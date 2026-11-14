from typing import Any

from app.ai.confidence.schema import ConfidenceResult, DecisionEnum
from app.ai.intent.schema import IntentEnum, IntentResult
from app.ai.planner.planner import ExecutedPlan
from app.core.config import settings


class ConfidenceEvaluator:
    """Evaluates multi-signal confidence to determine whether AI can safely answer or must escalate."""

    @classmethod
    def evaluate(
        cls,
        intent: IntentResult,
        executed_plan: ExecutedPlan | None = None,
        retrieved_chunks: list[tuple[Any, float]] | None = None,
        threshold: float | None = None,
    ) -> ConfidenceResult:
        thresh = threshold if threshold is not None else settings.AI_CONFIDENCE_THRESHOLD
        reasons: list[str] = []
        signals: dict[str, float] = {}

        # 1. Immediate escalation trigger check
        if intent.intent == IntentEnum.HUMAN_AGENT:
            return ConfidenceResult(
                confidence_score=0.0,
                decision=DecisionEnum.ESCALATE,
                reasons=["Customer explicitly requested a human agent."],
                signals={"human_request": 0.0},
            )

        if executed_plan and executed_plan.plan.escalate:
            return ConfidenceResult(
                confidence_score=0.2,
                decision=DecisionEnum.ESCALATE,
                reasons=[executed_plan.plan.escalation_reason or "Plan flagged mandatory escalation."],
                signals={"plan_escalate": 0.2},
            )

        # 2. Intent signal
        intent_score = intent.confidence
        signals["intent_confidence"] = intent_score
        reasons.append(f"Intent '{intent.intent.value}' detected with confidence {intent_score:.2f}")

        # 3. Tool execution signal
        tool_score = 1.0
        if executed_plan and executed_plan.tool_results:
            successes = [r for r in executed_plan.tool_results if r.success]
            failures = [r for r in executed_plan.tool_results if not r.success]

            if any(r.data and isinstance(r.data, dict) and r.data.get("verification_required") for r in successes):
                tool_score = 0.9
                reasons.append("Order lookup is waiting on the customer's identity check; asking for it.")
            elif failures:
                tool_score = 0.4
                reasons.append(f"{len(failures)} tool execution(s) encountered errors.")
            elif any(
                r.data and isinstance(r.data, dict) and r.data.get("found") is False
                # A missing policy *record* is not a failure when the uploaded documents cover the topic.
                and not (r.tool_name == "policy_lookup" and retrieved_chunks)
                for r in successes
            ):
                tool_score = 0.55
                reasons.append("Tool executed but required record was not found.")
            else:
                tool_score = 0.95
                reasons.append(f"All {len(successes)} tool(s) executed successfully with authoritative data.")
        signals["tool_execution"] = tool_score

        # 4. RAG retrieval signal
        rag_score = 1.0
        if executed_plan and executed_plan.plan.requires_rag:
            has_tool_facts = bool(
                executed_plan.tool_results
                and any(
                    r.success and r.data and not (isinstance(r.data, dict) and r.data.get("found") is False)
                    for r in executed_plan.tool_results
                )
            )
            if not retrieved_chunks and has_tool_facts:
                # Knowledge search is only complementary when an authoritative tool already answered.
                rag_score = 0.85
                reasons.append("Authoritative tool data available; no extra knowledge documents needed.")
            elif not retrieved_chunks:
                rag_score = 0.35
                reasons.append("Knowledge retrieval was required but yielded 0 matching documents.")
            else:
                top_score = max(score for _, score in retrieved_chunks)
                # Every returned passage already cleared the relevance gate, so retrieval is a positive signal.
                rag_score = min(1.0, 0.7 + 0.3 * top_score)
                reasons.append(f"Knowledge retrieval found {len(retrieved_chunks)} chunks (top relevance: {top_score:.2f}).")
        signals["rag_relevance"] = rag_score

        # 5. Composite weighted scoring
        # Weighting: Intent 35%, Tool 40%, RAG 25%
        composite = (0.35 * intent_score) + (0.40 * tool_score) + (0.25 * rag_score)

        # Apply sentiment penalty for severe complaints
        # A complaint the documents can answer (e.g. a damaged item -> the damaged-product process) is answered with
        # empathy; only a complaint with no supporting evidence is capped below the answer threshold and handed over.
        # Severe complaints (legal threats, payment disputes) are escalated by the router/planner before this point.
        if intent.intent == IntentEnum.COMPLAINT and not retrieved_chunks:
            composite = min(composite, 0.65)
            reasons.append("Complaint sentiment detected with no supporting policy evidence; capped confidence score.")

        # Nothing grounds this answer at all (no tool data, no knowledge): never auto-answer.
        grounded_by_tools = bool(executed_plan and executed_plan.tool_results)
        if (
            executed_plan
            and executed_plan.plan.requires_rag
            and not retrieved_chunks
            and not grounded_by_tools
        ):
            composite = min(composite, 0.55)
            reasons.append("No tool data or knowledge matched the question; capped confidence.")

        composite = round(min(1.0, max(0.0, composite)), 2)

        # 6. Decision gating
        if composite >= thresh:
            decision = DecisionEnum.ANSWER
        elif composite >= (thresh - 0.15):
            decision = DecisionEnum.ESCALATE
        else:
            decision = DecisionEnum.ESCALATE

        return ConfidenceResult(
            confidence_score=composite,
            decision=decision,
            reasons=reasons,
            signals=signals,
        )
