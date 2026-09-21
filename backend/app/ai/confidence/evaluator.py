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

            if failures:
                tool_score = 0.4
                reasons.append(f"{len(failures)} tool execution(s) encountered errors.")
            elif any(r.data and isinstance(r.data, dict) and r.data.get("found") is False for r in successes):
                tool_score = 0.55
                reasons.append("Tool executed but required record was not found.")
            else:
                tool_score = 0.95
                reasons.append(f"All {len(successes)} tool(s) executed successfully with authoritative data.")
        signals["tool_execution"] = tool_score

        # 4. RAG retrieval signal
        rag_score = 1.0
        if executed_plan and executed_plan.plan.requires_rag:
            if not retrieved_chunks:
                rag_score = 0.35
                reasons.append("Knowledge retrieval was required but yielded 0 matching documents.")
            else:
                top_score = max(score for _, score in retrieved_chunks)
                rag_score = min(1.0, max(0.2, top_score))
                reasons.append(f"Knowledge retrieval found {len(retrieved_chunks)} chunks (top relevance: {top_score:.2f}).")
        signals["rag_relevance"] = rag_score

        # 5. Composite weighted scoring
        # Weighting: Intent 35%, Tool 40%, RAG 25%
        composite = (0.35 * intent_score) + (0.40 * tool_score) + (0.25 * rag_score)

        # Apply sentiment penalty for severe complaints
        if intent.intent == IntentEnum.COMPLAINT:
            composite = min(composite, 0.65)
            reasons.append("Complaint sentiment detected; capped confidence score.")

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
