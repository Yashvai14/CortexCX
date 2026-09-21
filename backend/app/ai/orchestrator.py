import time
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

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
from app.rag.context import RAGContextAssembler
from app.rag.retrieval import RAGRetriever


class ConversationOrchestrator:
    """Master AI Conversation Orchestrator executing the complete CortexCX cognitive pipeline."""

    @classmethod
    def process_turn(
        cls,
        db: Session,
        workspace_id: UUID,
        conversation: Conversation,
        customer_message_content: str,
        customer: Customer | None = None,
        prompt_override: str | None = None,
    ) -> ChannelResponse:
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

        if not conversation.ai_enabled or active_escalation:
            conversation.ai_state = "escalated"
            db.commit()
            return ChannelResponse(
                conversation_id=conversation.id,
                content="Your message has been forwarded to your assigned support agent, who is reviewing the conversation and will reply shortly.",
                ai_state="escalated",
                decision="ESCALATE",
                confidence_score=1.0,
                sources=[],
                escalated=True,
            )

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

        # 4. AI Planner (Task decomposition & tool selection)
        plan = AIPlanner.create_plan(
            query=customer_message_content,
            intent=intent_res,
            memories=relevant_memories,
        )

        # 5. Tool Execution
        executed_plan = AIPlanner.execute_plan(
            db=db,
            workspace_id=workspace_id,
            plan=plan,
        )

        # 6. Hybrid Knowledge Retrieval (if planned or complementary)
        retrieved_chunks = []
        if plan.requires_rag:
            retriever = RAGRetriever()
            retrieved_chunks = retriever.retrieve(
                db=db,
                workspace_id=workspace_id,
                query=customer_message_content,
                top_k=4,
            )

        # 7. Multi-Signal Confidence Evaluation
        confidence = ConfidenceEvaluator.evaluate(
            intent=intent_res,
            executed_plan=executed_plan,
            retrieved_chunks=retrieved_chunks,
        )

        provider = get_llm_provider()
        model_name = getattr(provider, "model_name", provider.__class__.__name__)

        # 8. Decision Branching: ANSWER vs. ESCALATE
        if confidence.decision == DecisionEnum.ESCALATE or plan.escalate:
            # Create Human Escalation
            escalation_reason = (
                plan.escalation_reason
                if plan.escalate and plan.escalation_reason
                else f"Confidence ({confidence.confidence_score:.2f}) below threshold: " + "; ".join(confidence.reasons)
            )

            # Generate draft summary and suggested reply for agent assist
            summary_draft = f"Customer inquiry: '{customer_message_content}'. Intent: {intent_res.intent.value}."
            suggested_draft = (
                "Hello, I see your request regarding this matter. I am reviewing your account details and will assist you shortly."
            )

            escalation = HumanEscalation(
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                customer_id=customer_id,
                status=EscalationStatus.PENDING,
                reason=escalation_reason,
                confidence_score=confidence.confidence_score,
                summary=summary_draft,
                suggested_reply=suggested_draft,
            )
            db.add(escalation)

            # Update conversation state
            conversation.ai_state = "escalated"
            db.commit()

            escalation_msg_content = (
                "I have connected you with our human support team for personalized assistance. "
                "An agent has received your conversation history and will reply shortly."
            )

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
                confidence_score=confidence.confidence_score,
                tools_executed=[{"tool": r.tool_name, "success": r.success} for r in executed_plan.tool_results],
                retrieved_sources=[],
                model_name=model_name,
                duration_ms=duration_ms,
            )
            db.add(trace)
            db.commit()

            return ChannelResponse(
                conversation_id=conversation.id,
                content=escalation_msg_content,
                ai_state="escalated",
                decision="ESCALATE",
                confidence_score=confidence.confidence_score,
                sources=[],
                escalated=True,
            )

        # 9. Decision == ANSWER: Assemble safe grounded context & generate LLM response
        grounded_context = RAGContextAssembler.build_grounded_instruction(
            retrieved_chunks=retrieved_chunks,
            tool_context=executed_plan.summary_context,
            customer_memories=relevant_memories,
            prompt_override=prompt_override,
        )

        # Prepare message history
        messages_history = [
            {"sender_type": m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type), "content": m.content}
            for m in conversation.messages[-6:]
        ]
        if not messages_history:
            messages_history = [{"sender_type": "customer", "content": customer_message_content}]

        try:
            ai_response_text = provider.generate_response(
                conversation_subject=conversation.subject,
                messages=messages_history,
                prompt_override=grounded_context,
            )
        except Exception as e:
            # Fallback message
            ai_response_text = (
                "Thank you for reaching out. We have received your inquiry and our support team is reviewing it."
            )

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

        # Format sources
        sources = []
        for chunk, score in retrieved_chunks:
            sources.append({
                "chunk_id": str(chunk.id),
                "document_title": chunk.document.title if chunk.document else "Doc",
                "score": score,
            })

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

        return ChannelResponse(
            conversation_id=conversation.id,
            content=ai_response_text,
            ai_state="responded",
            decision="ANSWER",
            confidence_score=confidence.confidence_score,
            sources=sources,
            escalated=False,
        )
