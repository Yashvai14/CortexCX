"""Deterministic, fact-grounded reply composer.

Used (1) by the mock provider so development output is a real answer built from the
tool results / policies / knowledge, never a dump of the prompt, and (2) as the graceful
fallback when the LLM provider is unreachable, so customers still get a useful reply
instead of a generic "we received your inquiry".
"""
import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.intent.schema import IntentEnum
from app.ai.text_utils import extract_order_number, keywords, retrieval_terms, stem

STATUS_PHRASE = {
    "pending": "received and waiting to be processed",
    "processing": "being prepared for dispatch",
    "shipped": "on its way to you",
    "delivered": "marked as delivered",
    "cancelled": "cancelled",
    "refunded": "refunded",
}


@dataclass
class Grounding:
    intent: IntentEnum = IntentEnum.OTHER
    entities: dict[str, Any] = field(default_factory=dict)
    tool_results: list[Any] = field(default_factory=list)  # ToolResult
    chunks: list[tuple[Any, float]] = field(default_factory=list)  # (DocumentChunk, score)
    memories: list[str] = field(default_factory=list)
    customer_name: str | None = None
    store_name: str | None = None
    last_message: str = ""
    no_knowledge: bool = False  # the documents had nothing relevant for this question
    broad: bool = False         # broad overview question ("what is your refund policy?")


def _money(amount: Any, currency: str | None = "USD") -> str:
    try:
        sym = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get((currency or "USD").upper(), "")
        val = f"{float(amount):,.2f}".rstrip("0").rstrip(".") if float(amount) % 1 else f"{int(float(amount)):,}"
        return f"{sym}{val}" if sym else f"{val} {currency}"
    except (TypeError, ValueError):
        return str(amount)


def _first_name(name: str | None) -> str | None:
    if not name:
        return None
    first = name.split()[0]
    if first.lower() in {"store", "web", "guest", "probe", "customer"}:
        return None
    return first


def _tool(g: Grounding, name: str):
    for r in g.tool_results:
        if r.tool_name == name:
            return r
    return None


def _best_excerpt(chunks: list[tuple[Any, float]], query: str, max_sentences: int = 2) -> tuple[str, str] | None:
    """Pick the sentences of the retrieved chunks that best overlap the question."""
    q_terms = {stem(t) for t in keywords(query, 10)}
    best: tuple[float, str, str] | None = None
    for chunk, score in chunks:
        title = chunk.document.title if getattr(chunk, "document", None) and chunk.document.title else "our help center"
        sentences = re.split(r"(?<=[.!?])\s+|\n+", chunk.content.strip())
        for i, s in enumerate(sentences):
            s_terms = {stem(t) for t in keywords(s, 30)}
            overlap = len(q_terms & s_terms)
            if overlap == 0:
                continue
            rank = overlap + 0.2 * score
            if best is None or rank > best[0]:
                window = " ".join(x.strip() for x in sentences[i : i + max_sentences] if x.strip())
                best = (rank, window, title)
    if best:
        return best[1], best[2]
    return None


def _memory_note(g: Grounding) -> str:
    for m in g.memories:
        low = m.lower()
        if "allerg" in low or "sensitive" in low:
            topic = m.split(":", 1)[-1].strip()
            return f" I've also kept your note about {topic} in mind."
    return ""


def compose_reply(g: Grounding) -> str:
    text = _compose(g)
    return text[:1].upper() + text[1:] if text else text


def compose_grounded(g: Grounding) -> str | None:
    """Like compose_reply, but returns None when the sources hold nothing to say (never a generic non-answer)."""
    text = _compose(g, strict=True)
    return text[:1].upper() + text[1:] if text else None


def _compose(g: Grounding, strict: bool = False) -> str | None:
    name = _first_name(g.customer_name)
    hi = f"Hi {name}, " if name else ""
    intent = g.intent
    msg = g.last_message

    if g.entities.get("smalltalk"):
        low = msg.lower()
        if any(w in low for w in ("thank", "thx", "cheers", "great")):
            return f"{hi}you're very welcome! Is there anything else I can help with?"
        return f"{hi}welcome{' to ' + g.store_name if g.store_name else ''}! I can track orders, check stock, share discounts and explain our policies. What can I help you with?"

    # ── Orders ────────────────────────────────────────────────────
    if intent in (IntentEnum.ORDER_STATUS, IntentEnum.ORDER_CANCELLATION):
        t = _tool(g, "order_tracking")
        order_ref = g.entities.get("order_number")
        if not order_ref:
            what = "see whether it can still be cancelled" if intent == IntentEnum.ORDER_CANCELLATION else (
                "check where your refund stands" if g.entities.get("refund_status") else
                "look into the refund" if g.entities.get("refund_request") else "check it")
            return (
                f"{hi}happy to help. What's your order number? It looks like ORD-1001 and is in your "
                f"confirmation email. Once I have it I can {what}."
            )
        if t and t.success and t.data and t.data.get("found"):
            o = t.data["order"]
            status = o["status"]
            if g.entities.get("refund_request"):
                # An actual refund needs a person's approval: say so and OFFER the team (nothing is escalated yet).
                if status == "refunded":
                    return f"{hi}order {o['order_number']} has already been refunded. Is there anything else I can check?"
                return (
                    f"{hi}I can see order {o['order_number']}, which is {STATUS_PHRASE.get(status, status)}. Refunds need "
                    "approval from our team. Would you like me to bring in the team to process this refund request?"
                )
            if g.entities.get("refund_status"):
                # A refund question is answered from the order record only; it is never answered with policy text.
                if status == "refunded":
                    return f"{hi}the refund for order {o['order_number']} has been processed. Is there anything else I can check for you?"
                return (
                    f"{hi}order {o['order_number']} is {STATUS_PHRASE.get(status, status)}, and I can't see a refund "
                    "recorded on it from here. Would you like me to bring in the team to look into it?"
                )
            parts = [f"{hi}order {o['order_number']} is {STATUS_PHRASE.get(status, status)}."]
            if status == "shipped":
                carrier = f" with {o['carrier']}" if o.get("carrier") else ""
                if o.get("tracking_number"):
                    parts.append(f"It's travelling{carrier}, tracking number {o['tracking_number']}.")
                if o.get("estimated_delivery"):
                    parts.append(f"Estimated delivery: {o['estimated_delivery'][:10]}.")
            if o.get("items"):
                items = ", ".join(f"{i['quantity']}× {i['product_name']}" for i in o["items"][:3])
                parts.append(f"It contains {items}.")
            if intent == IntentEnum.ORDER_CANCELLATION:
                pol = _tool(g, "policy_lookup")
                if status in ("pending", "processing"):
                    parts.append("It hasn't shipped yet, so it may still be cancellable.")
                    if pol and pol.success and pol.data:
                        parts.append(pol.data["content"])
                    parts.append("Shall I ask the team to cancel it for you?")
                elif status in ("shipped", "delivered"):
                    parts.append(
                        "Because it has already left our warehouse it can't be cancelled, but you can refuse "
                        "delivery or return it once it arrives. Want me to explain how?"
                    )
                else:
                    parts.append("Nothing more needs cancelling on this one.")
            else:
                parts.append("Anything else I can check for you?")
            return " ".join(parts)
        if t and t.success and t.data and t.data.get("verification_required"):
            return (
                f"{hi}I can look into {order_ref}, but first I need to confirm it's yours. "
                "Please reply with the email address used at checkout."
            )
        return (
            f"{hi}I couldn't find an order matching {order_ref} with those details. Please double-check the "
            "order number and that the email is the one used at checkout. If it still doesn't match, "
            "I can check with my team to help."
        )

    # ── Catalog ───────────────────────────────────────────────────
    if intent in (IntentEnum.PRODUCT_SEARCH, IntentEnum.PRODUCT_INFORMATION):
        t = _tool(g, "product_search")
        products = (t.data if t and t.success and isinstance(t.data, list) else [])
        if not products:
            return (
                f"{hi}I couldn't find anything matching that in our catalog right now. "
                "Could you tell me a bit more, like the type, size or budget, and I'll look again?"
            )
        lines = []
        for p in products[:3]:
            stock = "in stock" if p["in_stock"] else "currently sold out"
            lines.append(f"{p['name']} ({_money(p['price'], p.get('currency'))}, {stock})")
        lead = "here's what I found: " if len(lines) > 1 else "I found "
        tail = "Would you like details on any of these?" if len(lines) > 1 else "Want me to tell you more about it?"
        return f"{hi}{lead}{'; '.join(lines)}.{_memory_note(g)} {tail}"

    if intent == IntentEnum.INVENTORY:
        t = _tool(g, "inventory_lookup")
        if t and t.success and t.data and t.data.get("found"):
            inv = t.data["inventory"]
            if not inv["in_stock"]:
                return f"{hi}{inv['product_name']} is sold out at the moment. I can note your interest so the team can let you know when it's back."
            extra = f" Only {inv['quantity_available']} left, so it's selling fast." if inv["low_stock"] else f" We have {inv['quantity_available']} available."
            return f"{hi}good news, {inv['product_name']} is in stock.{extra} Want help placing an order?"
        return (
            f"{hi}I couldn't match that to a product in our catalog. Could you share the exact product name "
            "or SKU so I can check the stock?"
        )

    # ── Offers ────────────────────────────────────────────────────
    if intent in (IntentEnum.COUPON, IntentEnum.DISCOUNT):
        t = _tool(g, "coupon_tool")
        d = t.data if t and t.success and isinstance(t.data, dict) else None
        if d and "valid" in d:
            if d["valid"]:
                return f"{hi}code {d['code']} is valid and gives you {d['description']}. Apply it at checkout."
            return f"{hi}that code didn't work: {d['reason']} Want me to look for another offer that fits?"
        if d and d.get("code"):
            val = d["discount_value"]
            off = f"{val:g}% off" if d.get("discount_type") == "percentage" else f"{_money(val)} off"
            return f"{hi}you can use {d['code']} for {off} at checkout. Anything else I can help with?"
        return f"{hi}there's no active offer I can confirm right now. I'll flag your request to the team if you'd like."

    # ── Policies & knowledge ──────────────────────────────────────
    if intent in (IntentEnum.POLICY, IntentEnum.REFUND, IntentEnum.RETURN, IntentEnum.DELIVERY):
        t = _tool(g, "policy_lookup")
        policy = t.data if t and t.success and isinstance(t.data, dict) and t.data.get('content') else None
        ex = _best_excerpt(g.chunks, msg)
        if re.search(r"\b(damaged|broken|defective|faulty|wrong item|wrong size|missing)\b", msg.lower()):
            order_ref = g.entities.get("order_number")
            ask = "" if order_ref else " Could you share your order number and, if you can, a photo of the damage?"
            body = f" {policy['content']}" if policy else ""
            return f"{hi}I'm so sorry it arrived like that.{body}{ask} I'll get a replacement or refund moving as soon as I have the details."
        if policy:
            body = policy["content"]
            extra = f" {ex[0]}" if ex and ex[0] not in body else ""
            tail = "Want help getting started?" if intent in (IntentEnum.REFUND, IntentEnum.RETURN) else "Is there anything else I can help with?"
            return f"{hi}here's our {policy['title'].lower().replace(' policy', '')} policy: {body}{extra} {tail}"
        if ex:
            return f"{hi}{ex[0]} Does that answer your question?"

    ex = _best_excerpt(g.chunks, msg)
    if ex:
        return f"{hi}{ex[0]} Is there anything else you'd like to know?"

    if intent == IntentEnum.COMPLAINT:
        return (
            f"{hi}I'm really sorry about this, that isn't the experience we want you to have. "
            "Could you tell me what happened and your order number? I'll make sure it's put right."
        )

    if strict:
        return None
    store = f" at {g.store_name}" if g.store_name else ""
    return (
        f"{hi}I want to give you an accurate answer, and I don't have that information to hand{store}. "
        "Could you share a little more detail, or I can check with my team?"
    )


def describe_topic(g: Grounding) -> str:
    return {
        IntentEnum.ORDER_STATUS: "an order status",
        IntentEnum.ORDER_CANCELLATION: "cancelling an order",
        IntentEnum.REFUND: "a refund",
        IntentEnum.RETURN: "a return or exchange",
        IntentEnum.COUPON: "a discount code",
        IntentEnum.DISCOUNT: "discounts",
        IntentEnum.INVENTORY: "product availability",
        IntentEnum.PRODUCT_SEARCH: "finding a product",
        IntentEnum.PRODUCT_INFORMATION: "product details",
        IntentEnum.DELIVERY: "shipping and delivery",
        IntentEnum.POLICY: "store policies",
        IntentEnum.COMPLAINT: "a problem with their purchase",
        IntentEnum.HUMAN_AGENT: "speaking with a person",
    }.get(g.intent, "their enquiry")


_IDENTITY_Q = re.compile(
    r"\b(?:are|r)\s+(?:you|u)\s+(?:a\s+|an\s+)?(?:real\s+|actual\s+)?"
    r"(?:bot|robot|ai|human|person|machine|chatbot|real|live|someone|automated)\b"
    r"|\bis\s+this\s+(?:a\s+)?(?:bot|robot|ai|human|chatbot|automated)\b"
    r"|\bam\s+i\s+(?:talking|chatting|speaking)\s+(?:to|with)\s+(?:a\s+)?(?:bot|robot|ai|human|person|machine)\b",
    re.I,
)


def is_identity_question(text: str) -> bool:
    return bool(_IDENTITY_Q.search(text or ""))


def identity_reply(agent_name: str, store: str | None) -> str:
    """Honest answer to "are you a bot / human?": a friendly persona is fine, claiming to be a person is not."""
    where = f" for {store}" if store else ""
    return (
        f"I'm {agent_name}, the virtual assistant{where}. I can help with orders, returns, refunds and our "
        "policies, and if you'd rather speak to someone on the team, just say so and I'll get a teammate on it."
    )


def customer_handoff_message(g: Grounding, reason: str = "") -> str:
    """What the customer sees when the AI hands the conversation to a human."""
    name = _first_name(g.customer_name)
    hi = f"{name}, " if name else ""
    if g.no_knowledge and g.intent != IntentEnum.HUMAN_AGENT:
        return (
            "Hmm, I couldn't find that in what I have in front of me, and I don't want to give you wrong "
            "information. Let me discuss it with my teammate - I'll get back to you right here shortly."
        )
    if g.intent == IntentEnum.HUMAN_AGENT:
        return (
            f"Sure, {hi}let me get my teammate on this right away. I've shared everything we've discussed, "
            "so you won't need to repeat yourself. We'll reply right here."
        )
    if g.intent == IntentEnum.COMPLAINT:
        return (
            f"I'm really sorry about this, {hi}and I want to get it sorted properly. I'm discussing it with my "
            "team right now and we'll get back to you here shortly."
        ).replace(", ,", ",")
    return (
        f"Let me double-check this with my team, {hi}so you get the right answer. "
        "I'll get back to you here shortly."
    ).replace(", ,", ",")


def build_agent_assist(g: Grounding, reason: str, history: list[dict[str, str]]) -> tuple[str, str]:
    """Context-rich (summary, suggested_reply) shown to the human agent on takeover."""
    who = g.customer_name or "The customer"
    bits = [f"{who} is asking about {describe_topic(g)}."]
    if g.entities.get("order_number"):
        bits.append(f"Order referenced: {g.entities['order_number']}.")
    for r in g.tool_results:
        if r.tool_name == "order_tracking" and r.success and r.data and r.data.get("found"):
            o = r.data["order"]
            bits.append(f"System shows {o['order_number']} as {o['status']}" + (f" via {o['carrier']}" if o.get("carrier") else "") + ".")
        elif r.tool_name == "order_tracking" and r.success and r.data and r.data.get("found") is False:
            if r.data.get("verification_required"):
                bits.append("Order details withheld: customer has not yet confirmed the checkout email.")
            else:
                bits.append("No order matched the number and email the customer gave.")
    if g.memories:
        bits.append("Known about this customer: " + "; ".join(m.rstrip(".") for m in g.memories[:3]) + ".")
    customer_msgs = [m["content"] for m in history if m.get("sender_type") == "customer"]
    if g.last_message and (not customer_msgs or customer_msgs[-1] != g.last_message):
        customer_msgs.append(g.last_message)
    if not g.entities.get("order_number"):
        for text in reversed(customer_msgs):
            ref = extract_order_number(text)
            if ref:
                bits.append(f"Order referenced earlier: {ref}.")
                break
    if len(customer_msgs) > 1:
        earlier = " | ".join(f'"{t[:140]}"' for t in customer_msgs[-4:-1])
        bits.append(f"Earlier in the conversation the customer said: {earlier}.")
    if customer_msgs:
        bits.append(f'Latest message: "{customer_msgs[-1][:200]}"')
    bits.append(f"Why the AI handed off: {reason}")
    summary = " ".join(bits)

    name = _first_name(g.customer_name)
    greet = f"Hi {name}," if name else "Hello,"
    grounded = compose_reply(g) if any(
        r.success and r.data for r in g.tool_results
    ) else ""
    if grounded and g.intent != IntentEnum.HUMAN_AGENT:
        suggested = grounded
    else:
        suggested = (
            f"{greet} this is a member of the support team. I've read through your conversation about "
            f"{describe_topic(g)} and I'm looking into it now. Could you confirm the order number and the best "
            "way to reach you if we get disconnected?"
        )
    return summary, suggested


_HEX = "[0-9a-fA-F]"
_UUID = f"{_HEX}{{8}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{4}}-{_HEX}{{12}}"


def sanitize_reply(text: str) -> str:
    """Last line of defence: never let an internal id reach a customer, whatever the model wrote."""
    # drop whole parentheticals that carry an id, e.g. "(product_id: <uuid>, SKU: X)"
    text = re.sub(r"\s*[(][^()]*" + _UUID + r"[^()]*[)]", "", text)
    text = re.sub(_UUID, "", text)
    text = re.sub(r"\b(?:product_id|order_id|customer_id|workspace_id|chunk_id)\b[:=]?\s*", "", text, flags=re.I)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def bulletize(text: str) -> str:
    """Readable layout for a longer answer the model wrote as one paragraph: lead sentence, then one bullet per point.

    Answers that already use lists, or are only one or two sentences, are returned unchanged.
    """
    if re.search(r"(?m)^\s*(?:[-*•]|\d+[.)])\s", text):
        return text
    text = re.sub(r"([.!?])\s+((?:\[\d+\])+)", r"\1\2", text.strip())  # keep trailing [n] citations on their sentence
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", text) if x.strip()]
    if len(sentences) < 3:
        return text
    return sentences[0] + "\n" + "\n".join(f"- {x}" for x in sentences[1:])


def plain_text(text: str) -> str:
    """Markdown-lite to plain text for channels without formatting (Telegram, SMS): no ** and real bullets."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    # Markdown tables have no plain-text form: drop the separator row and turn each row into "Cell: value" lines.
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if re.fullmatch(r"\|[\s:|-]+\|", stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            out.append("• " + (f"{cells[0]}: {' · '.join(cells[1:])}" if len(cells) > 1 else cells[0]))
        else:
            out.append(line)
    return re.sub(r"(?m)^(\s*)[-*]\s+", r"\1" + "• ", "\n".join(out))


# ── Faithfulness guard ─────────────────────────────────────────────
_SUPPORT_WORDS = frozenset(
    """help helps happy glad sorry please thanks thank let know team teammate contact reach anything else need
    questions question further assist assistance welcome hello hi sure certainly yes order orders""".split()
)


def _numbers(text: str) -> set[str]:
    cleaned = re.sub(r"\[\d+\]", " ", text)  # drop citation markers like [1]
    # Step labels and list numbering ("Step 1", "2.", "3)") are structure, not facts the model could invent.
    cleaned = re.sub(r"\bsteps?\s+\d+\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"(?m)^\s*(?:[-*]\s*)?\d{1,2}[.)]\s", " ", cleaned)
    out = set()
    for tok in re.findall(r"\d[\d,]*(?:[.]\d+)?", cleaned):
        out.add(tok.replace(",", "").rstrip("."))
    return out


def answer_is_grounded(answer: str, material: str, question: str = "") -> tuple[bool, str]:
    """Cheap faithfulness check: every figure in the answer must appear in the material, and most of its
    content words must come from the material or the question. Catches small models inventing numbers/steps."""
    source = f"{material}\n{question}"
    unsupported = _numbers(answer) - _numbers(source)
    if unsupported:
        return False, f"unsupported figures: {sorted(unsupported)[:5]}"

    answer_terms = {t for t in retrieval_terms(re.sub(r"\[\d+\]", " ", answer)) if t not in _SUPPORT_WORDS}
    if len(answer_terms) >= 6:
        supported = answer_terms & set(retrieval_terms(source))
        ratio = len(supported) / len(answer_terms)
        if ratio < 0.5:
            return False, f"only {ratio:.0%} of the answer's content comes from the sources"
    return True, "ok"
