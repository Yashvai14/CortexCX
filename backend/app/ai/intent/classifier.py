import json
import re
from typing import Any

from app.ai.intent.schema import IntentEnum, IntentResult
from app.ai.providers.factory import get_llm_provider
from app.core.config import settings
from app.ai.text_utils import extract_order_number


class IntentClassifier:
    """Classifies customer intents and extracts key business entities."""

    INTENT_SYSTEM_PROMPT = """You are an intent classification and entity extraction engine for CortexCX, an AI Customer Experience system.
Analyze the customer's message and determine their primary intent from this list:
- PRODUCT_SEARCH: Customer searching for items, browsing products, or looking for recommendations.
- PRODUCT_INFORMATION: Asking for details, specifications, ingredients, sizing, or materials of a product.
- ORDER_STATUS: Tracking an order, asking where an order is, delivery ETA.
- ORDER_CANCELLATION: Requesting to cancel an order.
- REFUND: Requesting money back or asking about refund eligibility.
- RETURN: Inquiring about or initiating a product return or exchange.
- COUPON: Asking for a discount code, promo code, or voucher.
- DISCOUNT: Asking if sales, deals, or wholesale pricing is available.
- INVENTORY: Asking if an item is in stock, sold out, or when it will be restocked.
- DELIVERY: Asking about shipping carriers, rates, international shipping, delivery times.
- POLICY: Inquiring about store terms, return policy, privacy, or warranty.
- GENERAL_FAQ: General questions about the store, hours, contact info, or brand.
- HUMAN_AGENT: Explicitly asking to talk to a human, live person, supervisor, or real agent.
- COMPLAINT: Strong dissatisfaction, broken item, damaged package, bad service.
- OTHER: Unrelated or unclassifiable inquiries.

Respond ONLY with valid JSON in this format:
{
  "intent": "ORDER_STATUS",
  "confidence": 0.95,
  "entities": {
    "order_number": "ORD-1234"
  },
  "reasoning": "Customer specifically asked for status of order ORD-1234"
}"""

    @classmethod
    def classify(
        cls,
        text: str,
        history: list[dict[str, str]] | None = None,
    ) -> IntentResult:
        if not text or not text.strip():
            return IntentResult(
                intent=IntentEnum.OTHER,
                confidence=0.0,
                entities={},
                reasoning="Empty input message",
            )

        clean_text = text.strip()

        # Check for fast deterministic pattern matching first (or as fallback)
        heuristic_result = cls._heuristic_classify(clean_text)

        provider = get_llm_provider()
        provider_name = provider.__class__.__name__

        # If using MockLLMProvider, heuristic classification provides deterministic high fidelity
        if "Mock" in provider_name:
            return heuristic_result

        if not settings.AI_LLM_INTENT_CLASSIFICATION:
            return heuristic_result

        # A clear-cut heuristic match (specific keywords / order number / code) needs no second LLM call:
        # skipping it roughly halves reply latency on a local model. Vague messages still go to the LLM.
        if heuristic_result.confidence >= 0.85 and heuristic_result.intent not in (IntentEnum.OTHER, IntentEnum.GENERAL_FAQ):
            return heuristic_result

        # For OpenAI or Ollama, query structured completion
        try:
            prompt = f"Customer Message: \"{clean_text}\""
            if history:
                recent = history[-3:]
                context_str = "\n".join(f"{m.get('sender_type')}: {m.get('content')}" for m in recent)
                prompt = f"Recent Context:\n{context_str}\n\n{prompt}"

            raw_response = ""
            if hasattr(provider, "generate_raw"):
                raw_response = provider.generate_raw(
                    prompt=prompt,
                    system_instruction=cls.INTENT_SYSTEM_PROMPT,
                )
            else:
                raw_response = provider.generate_response(
                    conversation_subject="Intent Classification",
                    messages=[{"sender_type": "customer", "content": clean_text}],
                    prompt_override=cls.INTENT_SYSTEM_PROMPT,
                )

            # Clean json fences if present
            cleaned = raw_response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()

            parsed = json.loads(cleaned)
            intent_str = parsed.get("intent", "").upper()
            if intent_str in IntentEnum.__members__:
                # A small model readily over-reads a plain question as a complaint or a request for a human, which
                # triggers an unwarranted handoff. These two intents need keyword evidence as well.
                if intent_str in ("COMPLAINT", "HUMAN_AGENT") and heuristic_result.intent.value.upper() != intent_str:
                    return heuristic_result
                return IntentResult(
                    intent=IntentEnum[intent_str],
                    confidence=float(parsed.get("confidence", 0.8)),
                    entities=parsed.get("entities", {}),
                    reasoning=parsed.get("reasoning", ""),
                )
        except Exception:
            pass

        # Fallback to heuristic result
        return heuristic_result

    @classmethod
    def _heuristic_classify(cls, text: str) -> IntentResult:
        lower = text.lower()
        entities: dict[str, Any] = {}

        # 1. Human agent request
        if re.search(r"\b(human|agent|real person|representative|operator|live person|talk to (?:someone|somebody)|speak to (?:someone|somebody)|support person|supervisor|manager)\b", lower):
            return IntentResult(
                intent=IntentEnum.HUMAN_AGENT,
                confidence=0.98,
                entities={},
                reasoning="Customer explicitly requested a human agent or representative.",
            )

        # Extract order number pattern
        order_number = extract_order_number(text)
        if order_number:
            entities["order_number"] = order_number

        # 2. Order cancellation
        if any(w in lower for w in ["cancel my order", "cancel order", "cancellation", "cancel it", "cancel the order"]):
            return IntentResult(
                intent=IntentEnum.ORDER_CANCELLATION,
                confidence=0.94,
                entities=entities,
                reasoning="Customer requested order cancellation.",
            )

        # 3. Order status / tracking
        if re.search(r"\b(track|tracking|status|where is my|where's my|shipped|eta|delivered|delivery status|package|parcel|arrive|arrived)\b", lower) and ("order" in lower or "package" in lower or "parcel" in lower or entities.get("order_number")):
            return IntentResult(
                intent=IntentEnum.ORDER_STATUS,
                confidence=0.95,
                entities=entities,
                reasoning="Customer is inquiring about the delivery or status of an order.",
            )

        # 4. Refund / Return
        if any(w in lower for w in ["refund", "money back", "reimbursement"]):
            entities["policy_type"] = "refund"
            return IntentResult(
                intent=IntentEnum.REFUND,
                confidence=0.92,
                entities=entities,
                reasoning="Customer is inquiring about a refund or money back.",
            )
        if any(w in lower for w in ["return", "exchange", "send back"]):
            entities["policy_type"] = "return"
            return IntentResult(
                intent=IntentEnum.RETURN,
                confidence=0.92,
                entities=entities,
                reasoning="Customer is asking how to return or exchange an item.",
            )

        # 5. Coupon / Discount
        coupon_match = re.search(r"\bcode\s+([A-Za-z]{2,}[A-Za-z0-9_-]*\d[A-Za-z0-9_-]*|[A-Z0-9_-]{4,15})\b", text)
        if coupon_match:
            entities["code"] = coupon_match.group(1).upper()
            return IntentResult(
                intent=IntentEnum.COUPON,
                confidence=0.94,
                entities=entities,
                reasoning="Customer provided a promotional code to check.",
            )
        if any(w in lower for w in ["coupon", "promo code", "discount code", "voucher"]):
            return IntentResult(
                intent=IntentEnum.COUPON,
                confidence=0.93,
                entities=entities,
                reasoning="Customer is asking about or providing a promotional discount coupon.",
            )
        if any(w in lower for w in ["discount", "deal", "sale", "cheaper", "offer"]):
            return IntentResult(
                intent=IntentEnum.DISCOUNT,
                confidence=0.88,
                entities=entities,
                reasoning="Customer is asking for promotional discounts or sales.",
            )

        # 6. Inventory / In-stock
        if any(w in lower for w in ["in stock", "out of stock", "available", "inventory", "restock", "how many"]):
            return IntentResult(
                intent=IntentEnum.INVENTORY,
                confidence=0.90,
                entities=entities,
                reasoning="Customer is asking about stock availability.",
            )

        # 7. Delivery / Shipping
        if any(w in lower for w in ["shipping", "delivery time", "delivery fee", "ship to", "courier", "fedex", "ups"]):
            entities["policy_type"] = "shipping"
            return IntentResult(
                intent=IntentEnum.DELIVERY,
                confidence=0.89,
                entities=entities,
                reasoning="Customer is inquiring about shipping rates, options, or timing.",
            )

        # 8. Policy
        if any(w in lower for w in ["policy", "warranty", "terms", "guarantee"]):
            for p in ["return", "refund", "shipping", "warranty", "privacy"]:
                if p in lower:
                    entities["policy_type"] = p
                    break
            return IntentResult(
                intent=IntentEnum.POLICY,
                confidence=0.87,
                entities=entities,
                reasoning="Customer is inquiring about company policies.",
            )

        # 9. Complaint
        if any(w in lower for w in ["angry", "terrible", "worst", "unacceptable", "broken", "damaged", "scam", "disappointed", "complaint"]):
            return IntentResult(
                intent=IntentEnum.COMPLAINT,
                confidence=0.91,
                entities=entities,
                reasoning="Customer expressed dissatisfaction or submitted a complaint.",
            )

        # 10. Product search / Information
        if any(w in lower for w in ["looking for", "find", "search", "buy", "product", "recommend", "price", "how much", "cost of", "do you have", "show me"]):
            return IntentResult(
                intent=IntentEnum.PRODUCT_SEARCH,
                confidence=0.85,
                entities=entities,
                reasoning="Customer is looking for products or pricing.",
            )

        # 10b. Greetings / thanks (no knowledge needed, never an escalation)
        if re.fullmatch(r"\s*(hi|hii+|hello|hey|hey there|good (morning|afternoon|evening)|thanks|thank you( so much)?|thx|ok(ay)?|great,? thanks|cheers)[\s!.,]*", lower):
            entities["smalltalk"] = True
            return IntentResult(
                intent=IntentEnum.OTHER,
                confidence=0.95,
                entities=entities,
                reasoning="Greeting or thanks.",
            )

        # 10c. A concrete order reference with any problem wording is an order enquiry
        if entities.get("order_number"):
            return IntentResult(
                intent=IntentEnum.ORDER_STATUS,
                confidence=0.86,
                entities=entities,
                reasoning="Message references a specific order number.",
            )

        # 11. General FAQ / Other
        return IntentResult(
            intent=IntentEnum.GENERAL_FAQ if any(w in lower for w in ["who", "what", "where", "how", "when", "why", "help"]) else IntentEnum.OTHER,
            confidence=0.75,
            entities=entities,
            reasoning="General inquiry.",
        )
