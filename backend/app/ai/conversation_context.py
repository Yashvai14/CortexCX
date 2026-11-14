"""Short-term conversation memory.

Builds, per turn, exactly what the models need to understand a follow-up - and nothing more:
  * a sliding window of the most recent messages (CONV_WINDOW_MESSAGES),
  * a short extractive summary of everything older (no extra LLM call),
  * the current topic, entities mentioned (order numbers) and whether the assistant is waiting for details.

Conversation memory is context, never evidence: assistant messages in the window are labelled as such, and the
grounded-answer prompt states that earlier replies are not a source of company policy.
"""
import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.handoff import is_offer
from app.ai.routing.router import IntentRouter
from app.ai.routing.schema import KNOWLEDGE_INTENTS, Route, RouterIntent
from app.ai.text_utils import extract_order_number
from app.core.config import settings

_ASKS_FOR_DETAILS = re.compile(
    r"\b(?:what(?:'s| is) your order (?:number|id)|share (?:your|the) order|order (?:number|id)\?|could you (?:share|tell|confirm)|"
    r"can you (?:share|tell|confirm)|please (?:share|provide|send)|which (?:order|product|item))\b",
    re.I,
)


def _role(m: Any) -> str:
    s = m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type)
    return s.lower()


@dataclass
class ConversationContext:
    window: list[dict[str, str]] = field(default_factory=list)   # recent messages, oldest first
    summary: str | None = None                                    # extractive summary of older messages
    topic: RouterIntent | None = None                              # topic of the last knowledge-type message
    entities: dict[str, Any] = field(default_factory=dict)        # e.g. {"order_number": "ORD-1001"}
    awaiting_details: bool = False                                 # the assistant's last message asked for details
    last_assistant: str | None = None
    recent_assistant_texts: list[str] = field(default_factory=list)  # to avoid repeating ourselves
    # ---- lightweight conversation state (derived from the stored messages each turn; no extra table) ----
    conversation_id: Any = None
    current_intent: str | None = None            # set by the orchestrator once the message is routed
    previous_customer_message: str | None = None
    pending_question: str | None = None          # a question the assistant asked and the customer has not answered
    pending_action: str | None = None            # "offer_escalation" | "provide_details" | None
    escalation_status: str = "none"              # none | pending | in_progress
    last_processed_message_id: Any = None

    @property
    def previous_assistant_message(self) -> str | None:
        return self.last_assistant

    @property
    def conversation_summary(self) -> str | None:
        return self.summary

    def customer_history(self) -> list[str]:
        return [m["content"] for m in self.window if m["sender_type"] == "customer"]

    def for_model(self) -> list[dict[str, str]]:
        """Window for an LLM call, with the summary (if any) as a leading system note."""
        out: list[dict[str, str]] = []
        if self.summary:
            out.append({"sender_type": "system", "content": f"Earlier in this conversation: {self.summary}"})
        out.extend(self.window)
        return out


def _summarise(older: list[Any]) -> str | None:
    """Cheap extractive summary: topics the customer raised and identifiers they gave. No model call."""
    if not older:
        return None
    topics: list[str] = []
    entities: list[str] = []
    for m in older:
        if _role(m) != "customer":
            continue
        d = IntentRouter.route_by_rules(m.content)
        if d.intent in KNOWLEDGE_INTENTS or d.intent in (RouterIntent.ORDER_INFORMATION, RouterIntent.COMPLAINT):
            label = d.intent.value.replace("_", " ").lower()
            if label not in topics:
                topics.append(label)
        ref = extract_order_number(m.content)
        if ref and ref not in entities:
            entities.append(ref)
    parts = []
    if topics:
        parts.append("the customer asked about " + ", ".join(topics[-4:]))
    if entities:
        parts.append("they mentioned order " + ", ".join(entities[-2:]))
    if not parts:
        return None
    return ("; ".join(parts))[: settings.CONV_SUMMARY_MAX_CHARS]


def build_context(
    messages: list[Any],
    current_message: str,
    *,
    conversation_id: Any = None,
    escalation_status: str = "none",
) -> ConversationContext:
    """`messages` = the stored conversation (oldest first); the current customer message may or may not be in it."""
    msgs = list(messages)
    if msgs and _role(msgs[-1]) == "customer" and msgs[-1].content == current_message:
        msgs = msgs[:-1]  # the current message is handled separately

    size = max(2, settings.CONV_WINDOW_MESSAGES)
    older, recent = msgs[:-size], msgs[-size:]
    ctx = ConversationContext(
        window=[{"sender_type": _role(m), "content": m.content} for m in recent],
        summary=_summarise(older),
    )

    # topic = the most recent customer message that was about company knowledge or a complaint
    for m in reversed(msgs):
        if _role(m) != "customer":
            continue
        d = IntentRouter.route_by_rules(m.content)
        if d.intent in KNOWLEDGE_INTENTS or d.intent in (RouterIntent.ORDER_INFORMATION, RouterIntent.COMPLAINT):
            ctx.topic = d.topic or d.intent
            if d.entities.get("kind") in ("refund_request", "refund_status"):
                # "I want a refund" -> "what's your order number?" -> "ORD-1001": the last reply is still a refund request
                ctx.entities["order_flow_kind"] = d.entities["kind"]
            break
    for m in msgs:
        if _role(m) == "customer":
            ref = extract_order_number(m.content)
            if ref:
                ctx.entities["order_number"] = ref
    assistants = [m.content for m in msgs if _role(m) in ("ai", "agent")]
    ctx.recent_assistant_texts = assistants[-3:]
    ctx.last_assistant = assistants[-1] if assistants else None
    ctx.conversation_id = conversation_id
    ctx.escalation_status = escalation_status
    ctx.last_processed_message_id = getattr(msgs[-1], "id", None) if msgs else None
    customers = [m.content for m in msgs if _role(m) == "customer"]
    ctx.previous_customer_message = customers[-1] if customers else None
    if msgs and _role(msgs[-1]) in ("ai", "agent") and ctx.last_assistant:
        ctx.awaiting_details = bool(_ASKS_FOR_DETAILS.search(ctx.last_assistant))
        if is_offer(ctx.last_assistant):
            ctx.pending_action = "offer_escalation"       # the assistant offered the team; a yes/no answers it
        elif ctx.awaiting_details:
            ctx.pending_action = "provide_details"
        if ctx.last_assistant.rstrip().endswith("?"):
            ctx.pending_question = ctx.last_assistant.strip().split("\n")[-1][-200:]
    return ctx
