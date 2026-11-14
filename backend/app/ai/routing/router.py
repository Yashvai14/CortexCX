"""Intent router: decides DIRECT / RAG / TOOLS / ESCALATE for each customer message.

Stage 1 (always, microseconds, no model call): language rules built around *what the customer is doing* rather
than single keywords - asking vs. stating, sentiment with negation, domain topics, live-data cues, escalation
cues, follow-ups of the previous topic.
Stage 2 (only when stage 1 is unsure, and only with a real LLM): one small JSON classification call whose output is
validated against the router schema. A malformed or contradictory model answer is discarded and the stage-1
decision stands, so routing can never fail open into an unsafe path.
"""
import json
import re
from typing import Any

from loguru import logger

from app.ai.routing.schema import (
    DEFAULT_ROUTE, KNOWLEDGE_INTENTS, Route, RouterIntent, RoutingDecision, decision,
)
from app.ai.text_utils import extract_emails, extract_order_number
from app.core.config import settings

# ───────────────────────────── normalisation ──────────────────────────────
_WORD = re.compile(r"[a-z0-9']+")


def _norm(text: str) -> str:
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"(.)\1{2,}", r"\1\1", t)  # "heyyyy" -> "heyy"
    return re.sub(r"\s+", " ", t).strip()


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _any(pattern: re.Pattern[str], text: str) -> bool:
    return bool(pattern.search(text))


def _re(p: str) -> re.Pattern[str]:
    return re.compile(p, re.I)


# ───────────────────────────── conversational lexicons ─────────────────────
_GREETING = _re(
    r"^(?:hi+|hii+|hey+|heya|hello+|helo|hola|yo|namaste|namaskar|good\s*(?:morning|afternoon|evening|night)|gm|"
    r"howdy|greetings|sup|wassup|what'?s up|whats up)\b"
)
_HOW_ARE_YOU = _re(r"\bhow\s*(?:are|r)\s*(?:you|u)\b|\bhow'?s it going\b|\bhow do you do\b|\bkaise ho\b|\bkya haal\b")
_FAREWELL = _re(r"\b(?:bye+|goodbye|good night|see you|see ya|talk (?:to you )?later|take care|have a (?:nice|good|great) (?:day|one))\b")
_THANKS = _re(r"\b(?:thanks?|thank you|thankyou|thx|tysm|ty|cheers|much appreciated|appreciate it|dhanyavad|shukriya)\b")
_ACK = _re(
    r"^(?:ok+|okay+|okie|k+|kk|alright|all right|fine|sure|cool|noted|got it|understood|i see|i understand|"
    r"right|yes+|yeah|yep|yup|no|nope|nah|hmm+|oh+|ah+|oh i see|makes sense|that helps|that'?s helpful|"
    r"that works|perfect|sounds good|great)\b[\s!.,]*(?:thanks?|thank you)?[\s!.,]*$"
)
_IDENTITY = _re(
    r"\b(?:who are you|what(?:'s| is) your name|your name\??$|what are you|are (?:you|u) (?:a |an )?(?:real |actual )?"
    r"(?:bot|robot|ai|human|person|machine|chatbot|real|live|someone|automated)|is this (?:a )?(?:bot|robot|ai|human|"
    r"chatbot|automated)|am i (?:talking|chatting|speaking) (?:to|with) (?:a )?(?:bot|robot|ai|human|person|machine)|"
    r"who am i (?:talking|chatting|speaking) (?:to|with))\b"
)
_OPEN_CONVERSATION = _re(
    r"^(?:i|we)\s*(?:just\s*)?(?:want|wanna|would like|need|'d like)\s+to\s+(?:talk|chat|speak|discuss|ask something)\s*[.!]?$|"
    r"^(?:can|could) (?:we|i) (?:talk|chat|speak)\??$|^(?:i have|got) (?:a|one) (?:question|query|doubt|problem|issue)\s*[.!?]?$|"
    r"^(?:i )?need (?:some )?help\s*[.!?]?$|^help( me)?\s*[.!?]?$|^can you help( me)?\??$|^i have (?:a )?(?:small )?doubt\s*[.!?]?$|"
    r"^(?:can|may) i ask (?:you )?(?:something|a question)\??$"
)
_POSITIVE = frozenset(
    "good great nice amazing awesome love loved lovely perfect excellent wonderful beautiful fantastic happy "
    "satisfied best super fabulous comfortable impressed pleased superb brilliant fine cool gorgeous stylish "
    "quality worth fast quick quickly smooth easy helpful delighted".split()
)
_NEGATIVE = frozenset(
    "unhappy upset angry sad frustrated annoyed annoying bad terrible worst horrible disgusted disappointed "
    "disappointing worried stressed irritated irritating pathetic poor awful rubbish useless unsatisfied "
    "dissatisfied unacceptable ridiculous fed".split()
)
_NEGATION = _re(r"\b(?:not|n't|never|no|nothing|hardly|isn't|wasn't|aren't|weren't|don't|didn't|doesn't|cannot|can't)\b")

# ── conversational repair: the customer is correcting, confused, frustrated or apologising ─────────
_UNSOLICITED = _re(
    r"\bi (?:didn'?t|did not|never|haven'?t|have not) (?:say|said|ask|asked|write|wrote|type|typed|send|sent|text|message)\b"
    r"|\bi (?:didn'?t|did not) (?:say|ask for|want) (?:anything|that|this)\b|\bwhy (?:are|did|do) you (?:sending|send|keep sending|reply|replying|message|messaging|texting)\b"
    r"|\bi (?:haven'?t|have not) (?:asked|said) anything\b|\bnobody asked\b|\bwho asked\b"
)
_FRUSTRATION = _re(
    r"\byou(?:'re| are) not (?:understanding|listening|getting it|helping|answering)\b|\bnot understanding me\b|\bstop (?:repeating|sending|saying)\b"
    r"|\b(?:useless|stupid|pathetic) (?:bot|assistant|answer|reply|response)\b|\byou keep (?:repeating|saying|sending)\b|\bsame (?:thing|message|answer|reply) again\b|\bwaste of time\b"
)
_CORRECTION = _re(
    r"\bthat'?s not what i (?:asked|said|meant|wanted|was asking)\b|\bnot what i (?:asked|said|meant|wanted)\b|\bno,? that'?s (?:wrong|incorrect|not (?:right|correct|true))\b"
    r"|\bthat'?s (?:wrong|incorrect|not right|not correct|not true)\b|^no\b[,.! ]*(?:that|this|it)\b.*\b(?:wrong|incorrect|not)\b|\bwrong (?:answer|reply|response)\b"
    r"|\byou(?:'re| are) (?:wrong|mistaken|confused)\b|\bi (?:meant|said|was asking about|was talking about)\b|\bno,? i (?:meant|said|asked)\b|\bnot helpful\b|\bthat doesn'?t (?:answer|help)\b"
    r"|\bthat'?s not (?:it|right|helpful)\b|\byou misunderstood\b|\bmisunderstood me\b"
)
_CONFUSION = _re(
    r"\bi(?:'m| am) (?:confused|lost|not sure what you mean)\b|\bwhat do you mean\b|\bi (?:don'?t|do not) (?:understand|get (?:it|that|this))\b|\bi didn'?t (?:get|understand) (?:that|it|this)\b"
    r"|\b(?:can|could) you (?:explain|repeat|say|clarify|rephrase|simplify)\b|\bexplain (?:again|that|it|more|simply|better)\b|\bsay that again\b|\bcome again\b|^(?:what|huh|sorry what|pardon)\s*\?*$"
    r"|\bin (?:simple|simpler|easy|easier) (?:words|terms)\b|\bmore (?:simply|clearly)\b"
)
_APOLOGY = _re(r"^(?:oh )?(?:sorry|my bad|my mistake|apologies|oops|pardon me|my apologies)\b")
_REFUND_REQUEST = _re(
    r"\b(?:i|we)\s*(?:really\s*)?(?:want|need|would like|'d like|wanna|require|demand)\s+(?:to\s+(?:get|have|claim|request|receive)\s+)?(?:a|my|the|an)?\s*(?:full\s+)?(?:refund|money back|reimbursement)\b"
    r"|\brefund (?:me|my (?:order|money|payment|purchase)|this order)\b|\bgive me (?:a |my )?(?:refund|money back)\b|\bplease refund\b|\bwant my money back\b|\bi(?:'d| would) like (?:a |my )?refund\b"
    r"|\bi(?:'m| am) (?:requesting|asking for) (?:a )?refund\b|\brequest (?:a )?refund\b"
)
_AFFIRM = _re(r"^(?:yes+|yeah|yep|yup|sure|ok(?:ay)?|please(?: do)?|go ahead|do it|yes please|sure thing|that'?d be (?:great|good)|please connect|connect me|haan|ha)\b[\s!.,]*(?:please|thanks?|thank you)?[\s!.,]*$")
_DECLINE = _re(r"^(?:no+|nope|nah|not now|no thanks?|no thank you|never ?mind|don'?t|not needed|it'?s fine|its fine|i'?m fine|im fine|maybe later|later|nahi)\b[\s!.,]*(?:thanks?|thank you)?[\s!.,]*$")
_ONE_TOPIC_WORD = _re(r"^(?:returns?|refunds?|exchanges?|shipping|delivery|cancel(?:lation)?|warranty|payments?|policy|policies|replacement)\??$")

# ───────────────────────────── escalation cues ──────────────────────────────
_INJECTION = _re(
    r"\b(?:ignore|forget|disregard|override|bypass)\b.{0,40}\b(?:instruction|rule|polic|prompt|guideline|restriction)s?\b|"
    r"\b(?:system prompt|developer mode|jailbreak|act as|pretend (?:to be|you)|you are now)\b"
)
_INVENT = _re(r"\b(?:make up|invent|fake|fabricate|pretend|imagine|just guess|assume)\b.{0,50}\b(?:polic|rule|refund|return|price|discount|offer|term)")
_HUMAN = _re(
    r"\b(?:human|real person|live (?:agent|person|chat)|representative|operator|supervisor|manager|customer care "
    r"(?:executive|person)|support (?:agent|executive|person|team|staff)|someone (?:from|in) (?:the )?(?:team|support)|"
    r"(?:talk|speak|connect|chat|transfer|escalate)\b.{0,25}\b(?:someone|somebody|agent|person|team|staff))\b|"
    r"\b(?:connect|transfer|put|get) me\b.{0,30}\b(?:support|customer (?:care|service)|agent|team|someone|person|manager|executive)\b|"
    r"\b(?:talk|speak|chat) (?:to|with)\b.{0,15}\b(?:support|customer (?:care|support|service)|manager)\b|"
    r"\bcall me\b|\b(?:support|team|someone) (?:call|contact|phone|ring) me\b|\bcall me back\b"
)
_SEVERE = _re(
    r"\b(?:scam|scammed|fraud|fraudulent|cheat(?:ed|ing)?|lawyer|legal action|sue you|consumer (?:court|forum|complaint)|"
    r"police|chargeback|unauthori[sz]ed|charged twice|double[- ]charged|money (?:was |got |has been )?deducted|"
    r"payment (?:failed|deducted)|hacked|stolen|threat|harass\w*)\b"
)
_ACCOUNT_SENSITIVE = _re(r"\b(?:hacked|account (?:locked|blocked|suspended|compromised)|can't (?:log ?in|sign in)|cannot (?:log ?in|sign in)|otp (?:not|didn't)|delete my account)\b")

# ───────────────────────────── business topics ──────────────────────────────
_ORDER_WORD = _re(r"\b(?:orders?|parcel|package|shipment|consignment|awb|tracking)\b|\btrack\b|\bmy (?:order|parcel|package)\b")
_ORDER_CUE = _re(
    r"\bwhere(?:'s| is)? (?:my|the)\b|\btrack(?:ing)?\b|\bstatus\b|\bwhen (?:will|does|do|is)\b.*\b(?:arrive|reach|deliver|come|dispatch|ship)|"
    r"\b(?:not|hasn't|haven't|didn't|yet to|never)\b.{0,15}\b(?:arrive|arrived|received|receive|delivered|reach|shipped|dispatched)|"
    r"\b(?:delayed|delay|late|stuck|lost|missing)\b|\bcancel\b|\bdispatch(?:ed)?\b|\beta\b"
)
_REFUND_STATUS = _re(
    r"\b(?:has|have|is|was|did|when (?:will|do|does|is))\b.{0,25}\b(?:my )?refund\b.{0,25}\b(?:processed|issued|credited|done|initiated|received|approved|come|reach|status)\b|"
    r"\brefund status\b|\bstatus of (?:my )?refund\b|\bwhere(?:'s| is) my refund\b|\brefund (?:not|hasn't|haven't) (?:received|credited|come|arrived)\b"
)
_STOCK_PRICE = _re(
    r"\b(?:in stock|out of stock|stock|availability|available in|restock|back in stock|sizes? (?:available|do you have)|"
    r"is (?:this|it|the) .{0,30}available|current price|price of|prices?\b|how much (?:is|does|for|are)|cost of|what(?:'s| is) the cost)\b"
)
_PRODUCT_SEARCH = _re(r"\b(?:do you (?:have|sell|stock|carry|make)|looking for|show me|recommend|suggest|any (?:new )?(?:collection|arrivals?)|new arrivals?)\b")
_COUPON = _re(r"\b(?:coupon|promo(?:tion)? code|voucher|discount code|offer code|promo)\b|\bcode\s+[A-Za-z]{2,}[A-Za-z0-9_-]*\d")
_PRODUCT_INFO = _re(r"\b(?:material|fabric|cotton|size chart|sizing|sizes|fit|colou?rs?|wash(?:ing)?|care instructions?|product details?|specifications?|ingredients?|dimensions?)\b")

_TOPIC_PATTERNS: list[tuple[RouterIntent, re.Pattern[str]]] = [
    (RouterIntent.REFUND_POLICY, _re(r"\b(?:refunds?|refunded|money back|reimburse\w*)\b")),
    (RouterIntent.RETURN_POLICY, _re(r"\b(?:returns?|returned|returning|exchange[ds]?|exchanging|replace(?:ment|d)?|send (?:it )?back|swap|resize|different size)\b")),
    (RouterIntent.CANCELLATION_POLICY, _re(r"\bcancel\w*\b")),
    (RouterIntent.SHIPPING_POLICY, _re(r"\b(?:shipping|delivery|deliver\w*|dispatch\w*|courier|ship(?:s|ped)? to|international|pincode|cash on delivery|cod\b)")),
    (RouterIntent.WARRANTY_POLICY, _re(r"\b(?:warranty|guarantee|repair|defect(?:ive)?\s+policy)\b")),
    (RouterIntent.PAYMENT_INFORMATION, _re(r"\b(?:payments?|pay\b|upi|credit card|debit card|net ?banking|emi|wallet|gift cards?|invoice|gst|accepted cards?)\b")),
    (RouterIntent.COMPANY_INFORMATION, _re(
        r"\b(?:contact|phone|call you|email|e-mail|address|located|location|store hours|opening hours|working hours|"
        r"timings?|support hours|customer (?:care|support|service)|toll[- ]free|website|about (?:you|the company|your company)|"
        r"policy|policies|terms|conditions|privacy)\b")),
]
_PROBLEM = _re(
    r"\b(?:damaged|damage|defective|defect|faulty|torn|ripped|broken|broke|wrong (?:item|size|product|colou?r)|"
    r"incorrect|missing|stained|dirty|smell\w*|shrunk|fad(?:ed|ing)|not working|doesn't work|didn't work|expired|"
    r"fake|cheap quality|poor quality|bad quality|button|zip(?:per)?|stitch\w*|color bleed\w*)\b"
)
_ASK_CUE = _re(
    r"\?|^(?:what|how|when|where|why|who|which|can|could|may|do|does|did|is|are|am|will|would|should|shall)\b|"
    r"\b(?:i (?:want|need|would like|'d like|wish) to|please|tell me|let me know|help me|can you|could you|"
    r"want to know|wanted to know|wondering|i'm trying to|how to|how do i|how can i|any way)\b"
)
_FOLLOWUP_OPENER = _re(r"^(?:and|also|but|then|so|what about|how about|what if|and if|what happens|how long|how many|how much|is it|does it|can i|do i|will it|why)\b")

_DOMAIN_ANY = [p for _, p in _TOPIC_PATTERNS] + [_ORDER_WORD, _STOCK_PRICE, _PRODUCT_INFO, _COUPON]


def _has_domain(text: str) -> bool:
    return any(_any(p, text) for p in _DOMAIN_ANY)


def _topic_of(text: str) -> RouterIntent | None:
    for intent, pat in _TOPIC_PATTERNS:
        if _any(pat, text):
            return intent
    if _any(_PRODUCT_INFO, text):
        return RouterIntent.PRODUCT_INFORMATION
    return None


def _sentiment(text: str) -> str | None:
    """'positive' / 'negative' / None, with negation flipping the polarity ("not good", "wasn't great")."""
    ws = _words(text)
    pos = sum(1 for w in ws if w in _POSITIVE)
    neg = sum(1 for w in ws if w in _NEGATIVE)
    negated = _any(_NEGATION, text)
    if pos and negated and not neg:
        return "negative"
    if neg and not pos:
        return "negative"
    if neg and pos:
        return "negative" if neg >= pos else "positive"
    if pos:
        return "positive"
    return None


_ROUTE_ALIASES: dict[str, Route] = {
    "DIRECT": Route.DIRECT, "DIRECT_CONVERSATION": Route.DIRECT,
    "RAG": Route.RAG, "RAG_KNOWLEDGE": Route.RAG,
    "TOOLS": Route.TOOLS, "TOOL": Route.TOOLS, "BUSINESS_TOOL": Route.TOOLS,
    "ESCALATE": Route.ESCALATE, "HUMAN_ESCALATION": Route.ESCALATE,
    "CLARIFY": Route.CLARIFY, "CLARIFICATION": Route.CLARIFY,
}


class IntentRouter:
    """Stateless; construct once or use the classmethods."""

    # ----------------------------------------------------------------- stage 1
    @classmethod
    def route_by_rules(
        cls,
        text: str,
        *,
        previous_topic: RouterIntent | None = None,
        awaiting_details: bool = False,
        pending_action: str | None = None,
    ) -> RoutingDecision:
        raw = (text or "").strip()
        if not raw:
            return decision(RouterIntent.AMBIGUOUS_QUERY, 0.0, "empty message", route=Route.DIRECT, retrieval=False)
        t = _norm(raw)
        n_words = len(_words(t))
        asks = _any(_ASK_CUE, t)
        order_no = extract_order_number(raw)
        entities: dict[str, Any] = {"order_number": order_no} if order_no else {}

        # 0-. the assistant just OFFERED to bring in the team: a plain yes / no answers that offer
        if pending_action == "offer_escalation" and n_words <= 5:
            if _any(_DECLINE, t):
                return decision(RouterIntent.ACKNOWLEDGEMENT, 0.95, "declined the offer to bring in the team",
                                entities={**entities, "kind": "declined_offer"})
            if _any(_AFFIRM, t):
                return decision(RouterIntent.HUMAN_SUPPORT_REQUEST, 0.95, "accepted the offer to bring in the team",
                                entities={**entities, "accepted_offer": True})

        # 0. attempts to override the company's rules or to make the bot invent policy
        if _any(_INJECTION, t) or _any(_INVENT, t):
            return decision(RouterIntent.GENERAL_CONVERSATION, 0.97, "request to ignore rules or invent policy",
                            entities={**entities, "kind": "guardrail"})

        # 1a. "are you a bot / a human?" is a question about the assistant, not a request for a person
        if _any(_IDENTITY, t):
            return decision(RouterIntent.SMALL_TALK, 0.98, "asks who/what the assistant is",
                            entities={**entities, "kind": "identity"})

        # 1. a person is needed
        if _any(_HUMAN, t) and not _any(_OPEN_CONVERSATION, t):
            return decision(RouterIntent.HUMAN_SUPPORT_REQUEST, 0.97, "customer asked for a person",
                            entities=entities)
        if _any(_SEVERE, t):
            return decision(RouterIntent.COMPLAINT, 0.95, "dispute / legal / payment-security wording",
                            route=Route.ESCALATE, entities={**entities, "severe": True})
        if _any(_ACCOUNT_SENSITIVE, t):
            return decision(RouterIntent.ACCOUNT_SUPPORT, 0.93, "sensitive account problem",
                            route=Route.ESCALATE, entities=entities)

        # 1b. conversational repair: understood from what the customer is doing, never escalated
        if _any(_UNSOLICITED, t):
            return decision(RouterIntent.CORRECTION, 0.96, "says they did not ask / say anything",
                            entities={**entities, "kind": "unsolicited"})
        if _any(_FRUSTRATION, t):
            return decision(RouterIntent.CORRECTION, 0.95, "frustrated that the assistant is not understanding",
                            entities={**entities, "kind": "frustration"})
        if _any(_CORRECTION, t):
            return decision(RouterIntent.CORRECTION, 0.94, "says the previous answer was wrong / not what they asked",
                            entities={**entities, "kind": "correction"})
        if _any(_CONFUSION, t):
            return decision(RouterIntent.CONFUSION, 0.93, "confused or asks for the previous answer again",
                            entities={**entities, "kind": "confusion", "rephrase": bool(previous_topic)},
                            route=Route.RAG if previous_topic in KNOWLEDGE_INTENTS else Route.DIRECT,
                            follow_up=bool(previous_topic in KNOWLEDGE_INTENTS), topic=previous_topic)
        if _any(_APOLOGY, t) and n_words <= 6:
            return decision(RouterIntent.APOLOGY, 0.93, "customer apologises", entities={**entities, "kind": "apology"})

        # 2. purely social openers (honest, never searched)
        if _any(_OPEN_CONVERSATION, t):
            return decision(RouterIntent.GENERAL_CONVERSATION, 0.95, "wants to start talking / needs help",
                            entities={**entities, "kind": "open"})

        if _any(_ONE_TOPIC_WORD, t):
            return decision(RouterIntent.AMBIGUOUS_QUERY, 0.85, "a single topic word: policy question or request?",
                            entities={**entities, "kind": "clarify_topic", "topic_word": t.strip("?")})

        domain = _has_domain(t)
        sentiment = _sentiment(t)
        problem = _any(_PROBLEM, t)

        # 3. live business data (checked before policy so "where is my refund" is a status lookup)
        if extract_emails(raw) and previous_topic == RouterIntent.ORDER_INFORMATION and not asks:
            # an email address given after an order question is the identity check the assistant asked for
            return decision(RouterIntent.ORDER_INFORMATION, 0.9, "supplies the email for the order lookup",
                            entities=entities, follow_up=True, topic=RouterIntent.ORDER_INFORMATION)
        if _any(_REFUND_STATUS, t):
            return decision(RouterIntent.ORDER_INFORMATION, 0.93, "asks where their refund stands",
                            entities={**entities, "kind": "refund_status"})
        if _any(_REFUND_REQUEST, t) and not re.search(r"\b(?:policy|policies|process|procedure|how (?:do|does|long|can)|eligible|eligibility|conditions?)\b", t):
            return decision(RouterIntent.ORDER_INFORMATION, 0.9, "asks for an actual refund on an order",
                            entities={**entities, "kind": "refund_request"})
        if order_no or (_any(_ORDER_WORD, t) and _any(_ORDER_CUE, t) and (asks or problem or order_no)):
            # a question about the *rule* ("what is your order cancellation policy") is a document question
            if not re.search(r"\b(?:policy|policies|rules?|terms|conditions|process|procedure|charges?|fees?)\b", t) or order_no:
                return decision(RouterIntent.ORDER_INFORMATION, 0.93, "asks about their own order", entities=entities)
        if _any(_COUPON, t):
            return decision(RouterIntent.PRODUCT_INFORMATION, 0.9, "coupon / promo code check",
                            route=Route.TOOLS, entities={**entities, "kind": "coupon"})
        policy_words = _topic_of(t) in (
            RouterIntent.RETURN_POLICY, RouterIntent.REFUND_POLICY, RouterIntent.SHIPPING_POLICY,
            RouterIntent.CANCELLATION_POLICY, RouterIntent.WARRANTY_POLICY,
        )
        if (_any(_STOCK_PRICE, t) or _any(_PRODUCT_SEARCH, t)) and not policy_words and (asks or n_words <= 8):
            return decision(RouterIntent.PRODUCT_INFORMATION, 0.88, "live stock / price / catalogue question",
                            route=Route.TOOLS, entities=entities)

        # 4. feelings and compliments that are not questions (a domain word inside them is not a request)
        if sentiment and not asks and not _any(_GREETING, t):
            if sentiment == "positive" and not problem:
                return decision(RouterIntent.COMPLIMENT, 0.96, "positive feedback, nothing asked", entities=entities)
            if sentiment == "negative" and not (domain or problem):
                return decision(RouterIntent.EMOTIONAL_RESPONSE, 0.94, "unhappy, no specific issue yet", entities=entities)
            if sentiment == "negative":
                return decision(RouterIntent.COMPLAINT, 0.9, "unhappy about something specific",
                                entities={**entities, "problem": True})

        # 5. company knowledge
        topic = _topic_of(t)
        if problem and not asks and domain is False and previous_topic is None and n_words <= 14 and not sentiment:
            # "The shirt has a damaged button." -> a reported problem: explain the damaged-product process
            return decision(RouterIntent.COMPLAINT, 0.86, "reports a product problem",
                            entities={**entities, "problem": True})
        if topic and (asks or problem or n_words >= 3):
            if problem and not asks:
                return decision(RouterIntent.COMPLAINT, 0.88, "reports a problem with a purchase",
                                entities={**entities, "problem": True})
            return decision(topic, 0.92 if asks else 0.8, "asks about company policy / information",
                            entities=entities)
        if problem:
            return decision(RouterIntent.COMPLAINT if not asks else RouterIntent.RETURN_POLICY, 0.8,
                            "problem with an item", entities={**entities, "problem": bool(not asks)})
        if _any(_PRODUCT_SEARCH, t):
            return decision(RouterIntent.PRODUCT_INFORMATION, 0.82, "catalogue question", route=Route.TOOLS,
                            entities=entities)

        # 6. purely social messages
        if _any(_GREETING, t) or _any(_HOW_ARE_YOU, t):
            kind = "how_are_you" if _any(_HOW_ARE_YOU, t) else "greeting"
            return decision(RouterIntent.GREETING if kind == "greeting" else RouterIntent.SMALL_TALK, 0.97,
                            "greeting / how-are-you", entities={**entities, "kind": kind})
        if _any(_FAREWELL, t) and not asks:
            return decision(RouterIntent.SMALL_TALK, 0.95, "farewell", entities={**entities, "kind": "farewell"})
        if _any(_THANKS, t) and not asks:
            return decision(RouterIntent.ACKNOWLEDGEMENT, 0.97, "thanks", entities={**entities, "kind": "thanks"})
        if _any(_ACK, t):
            return decision(RouterIntent.ACKNOWLEDGEMENT, 0.9, "acknowledgement", entities={**entities, "kind": "ack"})
        if sentiment == "positive":
            return decision(RouterIntent.COMPLIMENT, 0.85, "positive remark", entities=entities)

        # 7. follow-up of the previous topic ("what about damaged products?", "how long does it take?")
        if previous_topic in KNOWLEDGE_INTENTS and asks and n_words <= 10 and (_any(_FOLLOWUP_OPENER, t) or not domain):
            return decision(previous_topic, 0.82, "follow-up question on the previous topic",
                            entities=entities, follow_up=True, topic=previous_topic)
        if awaiting_details and n_words <= 6 and not asks:
            # the assistant just asked for details (order id, date...) and this is the answer
            return decision(previous_topic or RouterIntent.ORDER_INFORMATION, 0.78, "supplies details the assistant asked for",
                            entities=entities, follow_up=True,
                            route=Route.TOOLS if (previous_topic in (None, RouterIntent.ORDER_INFORMATION)) else Route.RAG)

        # 8. remaining questions: company information, with low confidence so stage 2 may refine them
        if asks and n_words >= 3:
            return decision(RouterIntent.COMPANY_INFORMATION, 0.62, "question without a recognised topic",
                            entities=entities)
        if asks:
            return decision(RouterIntent.AMBIGUOUS_QUERY, 0.5, "very short question", entities={**entities, "kind": "clarify"})

        # 9. everything else is conversation, not a lookup
        return decision(RouterIntent.GENERAL_CONVERSATION, 0.72 if n_words <= 12 else 0.55,
                        "statement with no question or company topic", entities=entities)

    # ----------------------------------------------------------------- stage 2
    ROUTER_SYSTEM_PROMPT = (
        "You route messages for a customer-support assistant. Choose the processing path:\n"
        "DIRECT = ordinary conversation (greeting, thanks, compliment, feelings, small talk, chit-chat).\n"
        "RAG = needs the company's documents (policies, shipping, returns, refunds, payments, warranty, company info).\n"
        "TOOLS = needs live store data (a customer's order status, stock, current price, coupon, refund status).\n"
        "ESCALATE = a person must handle it (explicitly asks for a human, legal/payment dispute, account security). "
        "Never ESCALATE a greeting, thanks, correction, confusion or an ambiguous message.\n"
        "CLARIFY = too ambiguous to act on: ask one short clarifying question.\n"
        "Allowed intents: " + ", ".join(i.value for i in RouterIntent) + ".\n"
        'Reply with ONLY JSON: {"intent": "...", "route": "DIRECT|RAG|TOOLS|ESCALATE|CLARIFY", "confidence": 0.0-1.0, "reason": "..."}'
    )

    @classmethod
    def refine_with_llm(cls, text: str, history: list[dict[str, str]], base: RoutingDecision, stats: Any = None) -> RoutingDecision:
        """One validated JSON classification call. Any failure returns `base` unchanged."""
        from app.ai.providers.factory import get_llm_provider

        provider = get_llm_provider()
        if "Mock" in provider.__class__.__name__ or not hasattr(provider, "generate_raw"):
            return base
        try:
            recent = "\n".join(f"{m.get('sender_type')}: {str(m.get('content'))[:160]}" for m in history[-4:])
            prompt = (f"Recent conversation:\n{recent}\n\n" if recent else "") + f'Customer message: "{text[:400]}"'
            if stats is not None:
                stats.llm_calls += 1
            raw = provider.generate_raw(prompt=prompt, system_instruction=cls.ROUTER_SYSTEM_PROMPT)
            return cls.parse_llm_output(raw, base)
        except Exception as e:  # provider outage, timeout...
            logger.warning(f"router LLM step failed ({type(e).__name__}); keeping rule-based decision")
            return base

    @classmethod
    def parse_llm_output(cls, raw: str, base: RoutingDecision) -> RoutingDecision:
        """Validate a model's routing answer; malformed or contradictory output returns `base`."""
        try:
            cleaned = (raw or "").strip()
            if "```" in cleaned:
                cleaned = cleaned.split("```")[1].removeprefix("json").strip()
            start, end = cleaned.find("{"), cleaned.rfind("}")
            data = json.loads(cleaned[start:end + 1])
            intent = RouterIntent(str(data["intent"]).upper())
            route = _ROUTE_ALIASES[str(data["route"]).upper().strip()]
            conf = float(data.get("confidence", 0.7))
        except Exception:
            logger.warning("router LLM returned malformed output; keeping rule-based decision")
            return base
        # contradictions are rejected rather than trusted
        if route == Route.DIRECT and intent in KNOWLEDGE_INTENTS | {RouterIntent.ORDER_INFORMATION}:
            return base
        if route == Route.RAG and intent in (RouterIntent.GREETING, RouterIntent.COMPLIMENT, RouterIntent.ACKNOWLEDGEMENT):
            return base
        # the model may not downgrade an escalation / live-data decision made by the rules
        if base.route in (Route.ESCALATE, Route.TOOLS) and route in (Route.DIRECT, Route.RAG):
            return base
        if conf < 0.6:
            return base
        return decision(intent, conf, f"llm: {str(data.get('reason', ''))[:120]}", route=route,
                        entities=base.entities, follow_up=base.follow_up, topic=base.topic, source="llm")

    # ----------------------------------------------------------------- public
    @classmethod
    def route(
        cls,
        text: str,
        history: list[dict[str, str]] | None = None,
        *,
        previous_topic: RouterIntent | None = None,
        awaiting_details: bool = False,
        pending_action: str | None = None,
        stats: Any = None,
    ) -> RoutingDecision:
        base = cls.route_by_rules(text, previous_topic=previous_topic, awaiting_details=awaiting_details,
                                  pending_action=pending_action)
        if base.topic is None and base.intent in KNOWLEDGE_INTENTS:
            base = base.model_copy(update={"topic": base.intent})
        if settings.ROUTER_USE_LLM and base.confidence < settings.ROUTER_MIN_CONFIDENCE:
            base = cls.refine_with_llm(text, history or [], base, stats)
        return base


def has_explicit_topic(text: str) -> bool:
    """True when the message names a company-knowledge topic itself (return, refund, shipping...), i.e. it does not
    depend on earlier messages to be understood."""
    return _topic_of(_norm(text)) is not None


def looks_like_question(text: str) -> bool:
    """True for questions and requests ("Where is my order?", "I want to ..."), false for bare details ("ORD-1001")."""
    return _any(_ASK_CUE, _norm(text))
