import re
import time
from loguru import logger
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.ai.intent.schema import IntentEnum, IntentResult
from app.ai.text_utils import extract_emails, extract_order_number
from app.rag.context import NOT_IN_DOCUMENTS
from app.core.config import settings
from app.ai.answering import fallback_answer, finalize_answer
from app.ai.progress import emit
from app.ai.composer import Grounding, build_agent_assist, compose_reply, customer_handoff_message
from app.ai.conversation_context import ConversationContext, build_context
from app.ai.direct import respond_direct
from app.ai.handoff import INTERNAL_ERROR, TOOL_FAILURE, agent_ack, already_with_team, offer_text
from app.ai.outbound import enforce_outbound
from app.ai.metrics import TurnStats, log_turn, pipeline_metrics
from app.ai.rag_cache import answer_cache, cache_key, knowledge_version
from app.ai.routing import IntentRouter, KNOWLEDGE_INTENTS, Route, RouterIntent, RoutingDecision
from app.ai.routing.router import has_explicit_topic, looks_like_question
from app.rag.conflicts import detect_conflict
from app.ai.confidence import ConfidenceEvaluator, DecisionEnum
from app.ai.intent import IntentClassifier
from app.ai.planner import AIPlanner
from app.ai.providers.factory import get_llm_provider
from app.ai.trace_model import AIRunTrace
from app.channels.schema import ChannelResponse
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.model import Conversation
from app.customer.model import Customer
from app.escalation.model import EscalationStatus, HumanEscalation
from app.memory.service import CustomerMemoryService
from app.workspace.model import Workspace
from app.ticket import automation as ticket_auto
from app.ticket.model import TicketStatus
from datetime import datetime
from app.rag.context import RAGContextAssembler
from app.rag.retrieval import RAGRetriever


class ConversationOrchestrator:
    """Master AI Conversation Orchestrator executing the complete CortexCX cognitive pipeline."""

    @staticmethod
    def _resolve_followup(intent_res, conversation: Conversation, message: str):
        """A bare reply such as "it's me@x.com" continues the previous order question.

        When the current message supplies an email but no order number, and an earlier customer message
        in this conversation referenced an order, re-use that earlier intent and order number.
        """
        if intent_res.entities.get("order_number") or not extract_emails(message):
            return intent_res
        if intent_res.intent not in (IntentEnum.OTHER, IntentEnum.GENERAL_FAQ):
            return intent_res
        for m in reversed(conversation.messages):
            sender = m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type)
            if sender != "customer" or m.content == message:
                continue
            ref = extract_order_number(m.content)
            if ref:
                prev = IntentClassifier.classify(text=m.content)
                if prev.intent in (IntentEnum.ORDER_STATUS, IntentEnum.ORDER_CANCELLATION):
                    prev.entities["order_number"] = ref
                    return prev
                break
        return intent_res

    @staticmethod
    def _direct_turn(
        db: Session,
        workspace_id: UUID,
        conversation: Conversation,
        customer: Customer | None,
        message: str,
        route: RoutingDecision,
        ctx: ConversationContext,
        stats: TurnStats,
        start_time: float,
    ) -> ChannelResponse:
        """DIRECT path: ordinary conversation. No retrieval, no business tools, no confidence gate."""
        customer_id = customer.id if customer else conversation.customer_id
        if customer_id:
            # "my name is Raj" is worth remembering even in small talk; extraction is heuristic and cheap
            CustomerMemoryService.process_and_persist_extracted_memories(
                db=db, workspace_id=workspace_id, customer_id=customer_id,
                customer_message=message, conversation_id=conversation.id,
            )
        workspace = db.get(Workspace, workspace_id)
        customer_row = customer or (db.get(Customer, customer_id) if customer_id else None)
        provider = get_llm_provider()
        emit("writing")
        t0 = time.time()
        reply = respond_direct(
            route, message, ctx, provider,
            customer_name=customer_row.full_name if customer_row else None,
            store_name=workspace.name if workspace else None, stats=stats,
        )
        stats.llm_ms = int((time.time() - t0) * 1000) if reply.llm_used else 0
        stats.status = "fallback" if reply.fallback_reason else "ok"

        ai_msg = Message(conversation_id=conversation.id, sender_type=MessageSenderType.AI, content=reply.text)
        db.add(ai_msg)
        conversation.ai_state = "responded"
        db.commit()
        db.refresh(ai_msg)

        stats.total_ms = int((time.time() - start_time) * 1000)
        db.add(AIRunTrace(
            workspace_id=workspace_id, conversation_id=conversation.id, message_id=ai_msg.id,
            intent=route.intent.value, intent_confidence=route.confidence, decision="ANSWER",
            confidence_score=route.confidence, tools_executed=[], retrieved_sources=[],
            model_name=(getattr(provider, "model_name", provider.__class__.__name__) if reply.llm_used else "direct-template"),
            duration_ms=stats.total_ms,
        ))
        db.commit()
        log_turn(stats, conversation_id=conversation.id, message_id=ai_msg.id)
        return ChannelResponse(
            conversation_id=conversation.id, content=reply.text, ai_state="responded", decision="ANSWER",
            confidence_score=route.confidence, sources=[], escalated=False,
        )

    @staticmethod
    def _plain_reply(
        db: Session,
        workspace_id: UUID,
        conversation: Conversation,
        text: str,
        stats: TurnStats,
        start_time: float,
        *,
        escalated: bool = False,
        decision: str = "ANSWER",
        model: str = "system-message",
    ) -> ChannelResponse:
        """Persist and return a system-authored reply (offer, queue acknowledgement, failure notice)."""
        ai_msg = Message(conversation_id=conversation.id, sender_type=MessageSenderType.AI, content=text)
        db.add(ai_msg)
        conversation.ai_state = "escalated" if escalated else "responded"
        db.commit()
        db.refresh(ai_msg)
        stats.escalated = False if not escalated else stats.escalated
        stats.total_ms = int((time.time() - start_time) * 1000)
        db.add(AIRunTrace(
            workspace_id=workspace_id, conversation_id=conversation.id, message_id=ai_msg.id,
            intent=stats.intent, intent_confidence=stats.router_confidence, decision=decision,
            confidence_score=stats.router_confidence, tools_executed=[], retrieved_sources=[],
            model_name=model, duration_ms=stats.total_ms,
        ))
        db.commit()
        log_turn(stats, conversation_id=conversation.id, message_id=ai_msg.id)
        return ChannelResponse(
            conversation_id=conversation.id, content=text, ai_state="escalated" if escalated else "responded",
            decision=decision, confidence_score=stats.router_confidence, sources=[], escalated=escalated,
        )

    @staticmethod
    def _deliver_cached(db, workspace_id, conversation, hit, intent_res, route, stats, start_time) -> ChannelResponse:
        """Serve a validated answer to a repeated, context-free knowledge question without retrieval or an LLM call."""
        ai_msg = Message(conversation_id=conversation.id, sender_type=MessageSenderType.AI, content=hit.text)
        db.add(ai_msg)
        conversation.ai_state = "responded"
        db.commit()
        db.refresh(ai_msg)
        stats.total_ms = int((time.time() - start_time) * 1000)
        db.add(AIRunTrace(
            workspace_id=workspace_id, conversation_id=conversation.id, message_id=ai_msg.id,
            intent=route.intent.value, intent_confidence=route.confidence, decision="ANSWER",
            confidence_score=hit.confidence, tools_executed=[], retrieved_sources=hit.sources,
            model_name="answer-cache", duration_ms=stats.total_ms,
        ))
        db.commit()
        log_turn(stats, conversation_id=conversation.id, message_id=ai_msg.id)
        return ChannelResponse(
            conversation_id=conversation.id, content=hit.text, ai_state="responded", decision="ANSWER",
            confidence_score=hit.confidence, sources=hit.sources, suggestions=hit.suggestions, escalated=False,
        )

    @classmethod
    def process_turn(
        cls,
        db: Session,
        workspace_id: UUID,
        conversation: Conversation,
        customer_message_content: str,
        customer: Customer | None = None,
        prompt_override: str | None = None,
        forced_route: RoutingDecision | None = None,
    ) -> ChannelResponse:
        """`forced_route` is set by explicit UI actions (a Telegram button) so they start their workflow directly
        instead of being re-interpreted from text."""
        start_time = time.time()

        # 0. Check for active human escalation or AI disabled flag
        active_escalation = (
            db.query(HumanEscalation)
            .filter(
                HumanEscalation.conversation_id == conversation.id,
                HumanEscalation.status.in_([EscalationStatus.PENDING, EscalationStatus.IN_PROGRESS]),
            )
            .order_by(HumanEscalation.created_at.desc())
            .first()
        )

        # Agent marked it resolved and asked the customer to confirm - interpret this reply.
        if active_escalation and conversation.ai_state == ticket_auto.AWAITING_CONFIRMATION:
            verdict = ticket_auto.classify_confirmation(customer_message_content)
            if verdict in ("yes", "no"):
                if verdict == "yes":
                    reply, state, decision = "Wonderful - glad we could sort that out! I've closed this request. Ask me anything else anytime.", "idle", "RESOLVED"
                    active_escalation.status = EscalationStatus.RESOLVED
                    active_escalation.resolved_at = datetime.utcnow()
                    conversation.ai_enabled = True
                    ticket_auto.sync(db, conversation.id, TicketStatus.RESOLVED, "Customer confirmed the issue is resolved")
                else:
                    reply, state, decision = "Sorry about that - I've let my colleague know it isn't sorted yet and we'll follow up with you.", "escalated", "ESCALATE"
                    ticket_auto.sync(db, conversation.id, TicketStatus.IN_PROGRESS, "Customer said the issue is NOT resolved - reopened")
                conversation.ai_state = state
                db.add(Message(conversation_id=conversation.id, sender_type=MessageSenderType.AI, content=reply))
                db.commit()
                return ChannelResponse(
                    conversation_id=conversation.id, content=reply, ai_state=state, decision=decision,
                    confidence_score=1.0, sources=[], escalated=verdict == "no",
                )
            # Something else entirely: treat as a normal follow-up to the agent.
            conversation.ai_state = "escalated"

        # A person OWNS the conversation only once an agent has actually picked it up (or the AI was switched off).
        # A request that is merely waiting in the queue does NOT silence the assistant: it keeps helping normally.
        # (Before this, one unclaimed escalation made every later message - even "Hi" - return the same
        # "passed this on" line, because this branch ran before any routing.)
        agent_engaged = bool(active_escalation and (
            active_escalation.status == EscalationStatus.IN_PROGRESS or active_escalation.assigned_agent_id))
        escalation_state = "in_progress" if agent_engaged else ("pending" if active_escalation else "none")

        stats = TurnStats()
        ctx = build_context(conversation.messages, customer_message_content,
                            conversation_id=conversation.id, escalation_status=escalation_state)

        if agent_engaged or not conversation.ai_enabled:
            if active_escalation:
                ticket_auto.sync(db, conversation.id, TicketStatus.IN_PROGRESS, "Customer replied")
            stats.route, stats.intent, stats.router_reason = Route.ESCALATE.value, "WITH_AGENT", "agent owns the conversation"
            return cls._plain_reply(
                db, workspace_id, conversation, agent_ack(customer_message_content, ctx.recent_assistant_texts),
                stats, start_time, escalated=True, decision="ESCALATE",
            )

        # ── Hybrid routing: choose the path BEFORE spending any retrieval or model time ───────────────────
        # DIRECT_CONVERSATION / RAG_KNOWLEDGE / BUSINESS_TOOL / HUMAN_ESCALATION / CLARIFICATION
        route = forced_route or IntentRouter.route(
            customer_message_content, ctx.window, previous_topic=ctx.topic,
            awaiting_details=ctx.awaiting_details, pending_action=ctx.pending_action, stats=stats,
        )
        carried = ctx.entities.get("order_flow_kind")
        if (route.route == Route.TOOLS and route.intent == RouterIntent.ORDER_INFORMATION and carried
                and not route.entities.get("kind") and ctx.pending_action == "provide_details"
                and not looks_like_question(customer_message_content)):  # only bare details ("ORD-1001") continue the refund
            route = route.model_copy(update={"entities": {**route.entities, "kind": carried}})
        ctx.current_intent = route.intent.value
        stats.route, stats.intent = route.route.value, route.intent.value
        stats.router_confidence, stats.router_source, stats.router_reason = route.confidence, route.source, route.reason[:160]

        if route.route == Route.ESCALATE and active_escalation:
            # already queued for a person: do not open a second request or repeat the handoff announcement
            return cls._plain_reply(
                db, workspace_id, conversation, already_with_team(customer_message_content, ctx.recent_assistant_texts),
                stats, start_time, escalated=True, decision="ESCALATE",
            )

        if route.route in (Route.DIRECT, Route.CLARIFY):
            return cls._direct_turn(db, workspace_id, conversation, customer, customer_message_content, route, ctx, stats, start_time)

        # 1. Update AI state to processing
        conversation.ai_state = "processing"
        db.commit()


        # 2. Extract and persist any new customer memories (episodic facts)
        customer_id = customer.id if customer else conversation.customer_id
        if customer_id:
            CustomerMemoryService.process_and_persist_extracted_memories(
                db=db,
                workspace_id=workspace_id,
                customer_id=customer_id,
                customer_message=customer_message_content,
                conversation_id=conversation.id,
            )

        # Retrieve relevant memories for context assembly
        relevant_memories = []
        if customer_id:
            relevant_memories = CustomerMemoryService.get_relevant_memories(
                db=db,
                workspace_id=workspace_id,
                customer_id=customer_id,
                query=customer_message_content,
                limit=4,
            )

        # 3. Intent Detection & Entity Extraction
        intent_res = IntentClassifier.classify(text=customer_message_content)
        intent_res = cls._resolve_followup(intent_res, conversation, customer_message_content)

        _LIVE = (IntentEnum.ORDER_STATUS, IntentEnum.ORDER_CANCELLATION, IntentEnum.INVENTORY, IntentEnum.PRODUCT_SEARCH,
                 IntentEnum.COUPON, IntentEnum.DISCOUNT, IntentEnum.HUMAN_AGENT)
        if route.route == Route.RAG and intent_res.intent in _LIVE:
            # The keyword classifier saw "parcel"/"order"/"price" in what the router understood as a question about the
            # company's rules: answer from the documents, do not start an order lookup.
            as_intent = {
                RouterIntent.RETURN_POLICY: IntentEnum.RETURN, RouterIntent.REFUND_POLICY: IntentEnum.REFUND,
                RouterIntent.SHIPPING_POLICY: IntentEnum.DELIVERY, RouterIntent.COMPLAINT: IntentEnum.COMPLAINT,
                RouterIntent.CANCELLATION_POLICY: IntentEnum.POLICY, RouterIntent.WARRANTY_POLICY: IntentEnum.POLICY,
            }.get(route.intent, IntentEnum.GENERAL_FAQ)
            intent_res = IntentResult(intent=as_intent, confidence=0.8, entities={}, reasoning="Router: question about company rules.")

        if route.entities.get("kind") in ("refund_status", "refund_request"):
            # "Has my refund been processed?" / "I want a refund" concern the customer's own order, not refund policy
            intent_res = IntentResult(
                intent=IntentEnum.ORDER_STATUS, confidence=0.92,
                entities={**intent_res.entities, **route.entities, route.entities["kind"]: True,
                          **({"order_number": ref} if (ref := route.entities.get("order_number") or intent_res.entities.get("order_number")) else {})},
                reasoning="Refund status lookup on the customer's order.",
            )

        # 4. AI Planner (Task decomposition & tool selection)
        plan = AIPlanner.create_plan(
            query=customer_message_content,
            intent=intent_res,
            memories=relevant_memories,
        )

        if plan.escalate and route.route != Route.ESCALATE:
            # The planner's old keyword list ("agent", "manager", "terrible"...) fired on ordinary sentences. The router
            # understood the message and decided it needs no person, so plan it as a normal question instead.
            intent_res = IntentResult(intent=IntentEnum.GENERAL_FAQ, confidence=0.75, entities=intent_res.entities,
                                      reasoning="Router overrode a keyword-based escalation.")
            plan = AIPlanner.create_plan(query=customer_message_content, intent=intent_res, memories=relevant_memories)
        if route.route == Route.ESCALATE and not plan.escalate:
            plan.escalate = True
            plan.escalation_reason = f"Router: {route.reason}"
            plan.requires_rag = False

        # 5. Tool Execution
        customer_texts = [
            m.content for m in conversation.messages
            if (m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type)) == "customer"
        ] + [customer_message_content]
        executed_plan = AIPlanner.execute_plan(
            db=db,
            workspace_id=workspace_id,
            plan=plan,
            context={"_customer_id": customer_id, "_emails": extract_emails(*customer_texts)},
        )

        live_tools = {"order_tracking", "inventory_lookup", "product_search", "coupon_tool"}
        failed = [r for r in executed_plan.tool_results if r.tool_name in live_tools and not r.success and r.error]
        if failed and not any(r.success for r in executed_plan.tool_results if r.tool_name in live_tools):
            logger.error(f"business tool failure: {[(r.tool_name, r.error) for r in failed]}")
            stats.status = "error"
            return cls._plain_reply(db, workspace_id, conversation, TOOL_FAILURE, stats, start_time, model="tool-failure")

        # 6. Hybrid Knowledge Retrieval (if planned or complementary)
        retrieved_chunks = []
        broad_question = False
        query_topics: list[str] = []
        cache_k = kb_ver = None
        cacheable = (
            plan.requires_rag and all(st.tool_name == "policy_lookup" for st in plan.steps) and not relevant_memories and not route.follow_up
            and route.intent in KNOWLEDGE_INTENTS and has_explicit_topic(customer_message_content)
        )
        if cacheable:
            pipeline_metrics.note_cache_lookup()
            kb_ver = knowledge_version(db, workspace_id)
            cache_k = cache_key(workspace_id, customer_message_content)
            hit = answer_cache.get(cache_k, kb_ver)
            if hit is not None:
                stats.cache_hit = True
                return cls._deliver_cached(db, workspace_id, conversation, hit, intent_res, route, stats, start_time)
        conflict_unresolved = ""
        if plan.requires_rag:
            emit("searching")
            t_retrieval = time.time()
            retriever = RAGRetriever()
            # Earlier CUSTOMER messages of this conversation only (never assistant text, never other conversations)
            # let the retriever resolve "what about damaged products?" / "how long does it take?".
            retrieved_chunks, query_plan = retriever.retrieve_with_plan(
                db=db,
                workspace_id=workspace_id,
                query=customer_message_content,
                top_k=settings.RAG_CONTEXT_MAX_SPECIFIC,
                history=customer_texts[:-1][-4:],
            )
            broad_question = query_plan.broad
            query_topics = query_plan.topics
            stats.rag_invoked = True
            stats.retrieval_ms = int((time.time() - t_retrieval) * 1000)
            stats.retrieved_docs = len(retrieved_chunks)
            stats.top_relevance = max((sc for _, sc in retrieved_chunks), default=None)
            conflict = detect_conflict(retrieved_chunks)
            if conflict.conflict:
                stats.conflict = True
                logger.warning(f"policy conflict between documents ({'resolved' if conflict.resolved else 'UNRESOLVED'}): {conflict.detail}")
                if conflict.resolved:
                    retrieved_chunks = [(c, r) for c, r in retrieved_chunks if c.document_id in conflict.keep_documents]
                else:
                    conflict_unresolved = conflict.detail

        # 7. Multi-Signal Confidence Evaluation
        confidence = ConfidenceEvaluator.evaluate(
            intent=intent_res,
            executed_plan=executed_plan,
            retrieved_chunks=retrieved_chunks,
        )

        provider = get_llm_provider()
        model_name = getattr(provider, "model_name", provider.__class__.__name__)

        # Structured facts for the responder (used by the offline provider and as the LLM-failure fallback)
        workspace = db.get(Workspace, workspace_id)
        customer_row = customer or (db.get(Customer, customer_id) if customer_id else None)
        grounding = Grounding(
            intent=intent_res.intent,
            entities=intent_res.entities,
            tool_results=executed_plan.tool_results,
            chunks=retrieved_chunks,
            memories=relevant_memories,
            customer_name=customer_row.full_name if customer_row else None,
            store_name=workspace.name if workspace else None,
            last_message=customer_message_content,
            broad=broad_question,
        )
        history_for_assist = [
            {"sender_type": m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type), "content": m.content}
            for m in conversation.messages[-6:]
        ]

        # Documents had nothing relevant and no store data answered it: say so instead of letting the LLM guess
        grounding.no_knowledge = plan.requires_rag and not retrieved_chunks and not any(
            r.success and r.data and not (isinstance(r.data, dict) and r.data.get("found") is False)
            for r in executed_plan.tool_results
        )

        def escalate(escalation_reason: str, score: float) -> ChannelResponse:
            """Hand the conversation to a human with an agent-assist summary and draft reply."""
            if active_escalation:
                return cls._plain_reply(
                    db, workspace_id, conversation, already_with_team(customer_message_content, ctx.recent_assistant_texts),
                    stats, start_time, escalated=True, decision="ESCALATE",
                )
            stats.escalated = True
            try:
                # Generate draft summary and suggested reply for agent assist
                summary_draft, suggested_draft = build_agent_assist(grounding, escalation_reason, history_for_assist)

                escalation = HumanEscalation(
                    workspace_id=workspace_id,
                    conversation_id=conversation.id,
                    customer_id=customer_id,
                    status=EscalationStatus.PENDING,
                    reason=escalation_reason,
                    confidence_score=score,
                    summary=summary_draft,
                    suggested_reply=suggested_draft,
                )
                db.add(escalation)
                db.flush()
                ticket_auto.create_for_escalation(db, escalation, conversation)

                # Update conversation state
                conversation.ai_state = "escalated"
                db.commit()
            except Exception as e:
                # The handoff was NOT recorded, so the customer must not be told a teammate has been contacted.
                db.rollback()
                logger.error(f"escalation could not be recorded ({type(e).__name__}: {e})")
                stats.escalated, stats.status = False, "error"
                failure = ("I'm sorry, I'm having trouble reaching the team right now, so I can't confirm that anyone "
                           "has picked this up yet. Could you try again in a few minutes?")
                db.add(Message(conversation_id=conversation.id, sender_type=MessageSenderType.AI, content=failure))
                conversation.ai_state = "responded"
                db.commit()
                stats.total_ms = int((time.time() - start_time) * 1000)
                log_turn(stats, conversation_id=conversation.id)
                return ChannelResponse(
                    conversation_id=conversation.id, content=failure, ai_state="responded", decision="ANSWER",
                    confidence_score=score, sources=[], escalated=False,
                )

            escalation_msg_content = customer_handoff_message(grounding, escalation_reason)

            # Save escalation notice message
            ai_msg = Message(
                conversation_id=conversation.id,
                sender_type=MessageSenderType.AI,
                content=escalation_msg_content,
            )
            db.add(ai_msg)
            db.commit()
            db.refresh(ai_msg)

            duration_ms = int((time.time() - start_time) * 1000)

            # Record AI Run Trace
            trace = AIRunTrace(
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                message_id=ai_msg.id,
                intent=intent_res.intent.value,
                intent_confidence=intent_res.confidence,
                decision="ESCALATE",
                confidence_score=score,
                tools_executed=[{"tool": r.tool_name, "success": r.success} for r in executed_plan.tool_results],
                retrieved_sources=[],
                model_name=model_name,
                duration_ms=duration_ms,
            )
            db.add(trace)
            db.commit()
            stats.status = "escalated"
            stats.total_ms = int((time.time() - start_time) * 1000)
            log_turn(stats, conversation_id=conversation.id, message_id=ai_msg.id)

            return ChannelResponse(
                conversation_id=conversation.id,
                content=escalation_msg_content,
                ai_state="escalated",
                decision="ESCALATE",
                confidence_score=score,
                sources=[],
                escalated=True,
            )

        if conflict_unresolved:
            return escalate(f"Conflicting policy documents, no authoritative version: {conflict_unresolved}", 0.3)

        def offer_handoff(kind: str, reason: str) -> ChannelResponse:
            """The documents cannot settle this. Say so honestly and OFFER the team; escalate only if the customer
            accepts (their yes arrives as route HUMAN_ESCALATION). Low confidence alone never opens a request."""
            logger.info(f"offering handoff instead of escalating: {reason}")
            stats.status = "offer"
            return cls._plain_reply(
                db, workspace_id, conversation, offer_text(kind, customer_message_content, ctx.recent_assistant_texts),
                stats, start_time, model="offer-handoff",
            )

        # 8. Decision Branching. A person is involved only when the router / planner found a real reason (explicit
        # request, serious issue, authorisation needed). Mere uncertainty becomes an honest offer, never a ticket.
        if plan.escalate:
            return escalate(plan.escalation_reason or "Escalation requested.", confidence.confidence_score)
        if confidence.decision == DecisionEnum.ESCALATE:
            return offer_handoff(
                "complaint" if intent_res.intent == IntentEnum.COMPLAINT else "no_knowledge",
                f"Confidence ({confidence.confidence_score:.2f}): " + "; ".join(confidence.reasons),
            )

        # 9. Decision == ANSWER: Assemble safe grounded context & generate LLM response
        grounded_context = RAGContextAssembler.build_grounded_instruction(
            retrieved_chunks=retrieved_chunks,
            tool_context=executed_plan.summary_context,
            customer_memories=relevant_memories,
            prompt_override=prompt_override,
            broad=broad_question,
            topics=query_topics,
        )

        # Prepare message history
        # Sliding window + summary of older turns; the current message is always last. Earlier assistant replies are
        # context for understanding follow-ups, never evidence for company claims (the grounded prompt says so).
        messages_history = ctx.for_model() + [{"sender_type": "customer", "content": customer_message_content}]

        material = "\n".join(
            [executed_plan.summary_context or "", *[c.content for c, _ in retrieved_chunks], *relevant_memories,
             grounding.store_name or "", grounding.customer_name or ""]
        )
        emit("writing")
        t_llm = time.time()
        try:
            stats.llm_calls += 1
            raw_answer = provider.generate_response(
                conversation_subject=conversation.subject,
                messages=messages_history,
                prompt_override=grounded_context,
                grounding=grounding,
            )
            final = finalize_answer(
                raw_answer, grounding, retrieved_chunks, material, customer_message_content, workspace_id, db
            )
            stats.llm_ms = int((time.time() - t_llm) * 1000)
            if final.pasted and broad_question:
                # The model pasted the passages back. One more attempt, asking for what a customer wants: a short
                # overview in its own words. Keep it only if it validates and is actually shorter.
                stats.llm_calls += 1
                retry_raw = provider.generate_response(
                    conversation_subject=conversation.subject,
                    messages=messages_history,
                    prompt_override=grounded_context
                    + "\n\nIMPORTANT: your previous draft copied the passages. Rewrite it as a brief overview of at "
                    "most 120 words in your own words: no tables, no repeated lists, only the key points.",
                    grounding=grounding,
                )
                second = finalize_answer(
                    retry_raw, grounding, retrieved_chunks, material, customer_message_content, workspace_id, db
                )
                if not second.no_knowledge and not second.fallback and 0 < len(second.text) < len(final.text):
                    final = second
            if final.no_knowledge:
                # Nothing in the documents or store data supports an answer: hand off honestly instead of guessing.
                grounding.no_knowledge = True
                return offer_handoff("complaint" if intent_res.intent == IntentEnum.COMPLAINT else "no_knowledge",
                                     "documents do not contain an answer")
            if final.fallback:
                model_name = f"{model_name}+extractive-fallback"
        except Exception as e:
            # Do not hide provider outages: log them, then still answer from the retrieved passages / store facts.
            logger.error(f"LLM provider {model_name} failed ({type(e).__name__}: {e}); using grounded fallback reply")
            final = fallback_answer(grounding, retrieved_chunks, workspace_id, db)
            model_name = f"{model_name}+grounded-fallback"
        ai_response_text, outbound_issues = enforce_outbound(final.text, escalated=False)
        if outbound_issues:
            logger.warning(f"outbound reply corrected: {outbound_issues}")
        sources = final.sources
        degraded = bool(final.fallback) or "fallback" in model_name
        stats.grounded = not degraded
        stats.status = "fallback" if degraded else "ok"
        if cache_k and not degraded and ai_response_text:
            answer_cache.put(cache_k, kb_ver, ai_response_text, sources, final.suggestions, confidence.confidence_score)

        # 10. Persist AI message
        ai_msg = Message(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.AI,
            content=ai_response_text,
        )
        db.add(ai_msg)
        conversation.ai_state = "responded"
        db.commit()
        db.refresh(ai_msg)

        duration_ms = int((time.time() - start_time) * 1000)

        # Record AI Run Trace
        trace = AIRunTrace(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            message_id=ai_msg.id,
            intent=intent_res.intent.value,
            intent_confidence=intent_res.confidence,
            decision="ANSWER",
            confidence_score=confidence.confidence_score,
            tools_executed=[{"tool": r.tool_name, "success": r.success} for r in executed_plan.tool_results],
            retrieved_sources=sources,
            model_name=model_name,
            duration_ms=duration_ms,
        )
        db.add(trace)
        db.commit()
        stats.tools = [r.tool_name for r in executed_plan.tool_results]
        stats.total_ms = int((time.time() - start_time) * 1000)
        log_turn(stats, conversation_id=conversation.id, message_id=ai_msg.id)

        return ChannelResponse(
            conversation_id=conversation.id,
            content=ai_response_text,
            ai_state="responded",
            decision="ANSWER",
            confidence_score=confidence.confidence_score,
            sources=sources,
            suggestions=final.suggestions,
            escalated=False,
        )
