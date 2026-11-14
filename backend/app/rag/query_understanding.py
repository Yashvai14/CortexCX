"""Lightweight query understanding for retrieval (no LLM call).

Three jobs, all deterministic and cheap:

1. Conversation resolution. "How long does it take?" means nothing alone. When the latest customer message is a
   follow-up, it is combined with the previous customer question(s) so retrieval sees "refund timeline", not
   "it". Only the customer's own earlier questions are used, never assistant text or other conversations.
2. Vocabulary expansion. Customers say "torn", "money back", "wrong colour"; documents say "defective",
   "refund", "incorrect product". Generic customer-support synonym groups add the document-side wording to the
   keyword query. (Nothing here is specific to any company or policy.)
3. Specificity. A broad question ("what is your refund policy?") needs several sections of the same chapter; a
   specific one ("how long does a UPI refund take?") needs only the section that answers it.
"""
import re
from dataclasses import dataclass, field

from app.ai.text_utils import GENERAL_STOPWORDS, retrieval_terms, stem

# group -> (trigger phrases found in customer wording, terms to add for matching document wording)
_GROUPS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "refund": (
        ("refund", "money back", "get my money", "my money", "money comes back", "money come back", "money coming back",
         "reimburse", "paid back", "repay", "credited back", "reversal"),
        ("refund", "reimbursement", "money back", "refund approval"),
    ),
    "return": (
        ("return", "send back", "give back", "take back"),
        ("return", "return eligibility", "return request"),
    ),
    "exchange": (
        ("exchange", "swap", "replace", "replacement", "different size", "another size", "other size", "size change"),
        ("exchange", "replacement", "size", "exchange eligibility"),
    ),
    "cancel": (
        ("cancel", "cancellation", "call off", "dont want the order", "don't want the order"),
        ("cancellation", "cancel order", "before dispatch", "after dispatch"),
    ),
    "damaged": (
        ("torn", "ripped", "tear", "hole", "broken", "damaged", "defect", "defective", "faulty", "stain", "stitching",
         "came apart", "not working", "manufacturing"),
        ("damaged", "defective", "defect", "manufacturing defect", "evidence", "photographs"),
    ),
    "wrong": (
        ("wrong", "incorrect", "different from", "not what i ordered", "mismatch", "mixed up", "wrong colour",
         "wrong color", "wrong size"),
        ("incorrect product", "wrong item", "delivered", "replacement", "refund"),
    ),
    "missing": (
        ("missing", "not received", "only received", "fewer", "less than", "didn't get", "didnt get", "short",
         "two items instead", "instead of three"),
        ("missing items", "wrong quantity", "delivered", "evidence", "unboxing"),
    ),
    "timeline": (
        ("how long", "how many days", "how soon", "when will", "when do", "timeline", "how much time", "by when",
         "how fast", "time frame", "timeframe"),
        ("timeline", "business days", "processing", "estimated"),
    ),
    "payment": (
        ("paid", "payment", "upi", "card", "net banking", "netbanking", "wallet", "cod", "cash on delivery", "bank"),
        ("payment method", "bank"),
    ),
    "payment_failure": (
        ("failed", "failure", "deducted", "debited", "charged twice", "double charged", "money got", "not created",
         "order failed"),
        ("payment failure", "money deducted", "reconciliation", "refund"),
    ),
    "shipping_cost": (
        ("who pays", "shipping charge", "shipping fee", "delivery charge", "return shipping", "pickup fee",
         "courier charge", "postage"),
        ("shipping charges", "return shipping", "free", "pickup"),
    ),
    "pickup": (("pickup", "pick up", "collect", "courier", "self ship", "self-ship"), ("return pickup", "pickup", "logistics")),
    "nonreturnable": (
        ("innerwear", "underwear", "customised", "customized", "custom made", "personalised", "final sale",
         "non-returnable", "nonreturnable", "cannot be returned", "can't be returned", "clearance"),
        ("non-returnable", "products that cannot be returned", "innerwear", "customized clothing", "final sale"),
    ),
    "discount": (
        ("discount", "discounted", "on sale", "coupon", "promo", "offer", "bogo", "buy one get one", "bundle",
         "combo", "free gift"),
        ("discounted products", "promotional", "buy one get one", "coupon", "partial refund"),
    ),
    "condition": (
        ("washed", "wore", "worn", "used", "tag", "tags", "unboxing", "packaging", "perfume", "altered", "stained"),
        ("eligibility", "unused", "unworn", "original tags", "conditions", "quality inspection"),
    ),
    "inspection": (("inspect", "inspection", "quality check", "rejected", "fails"), ("quality inspection", "failed quality inspection", "rejection")),
    "support": (("contact", "support", "complain", "escalate", "speak to", "talk to", "email", "phone"), ("customer support", "escalation", "contact")),
}

# A message that names its own subject (damaged, cancel, exchange...) stands on its own for retrieval; the
# earlier turns still reach the LLM as conversation history. Qualifier-only messages ("how long?", "what if I paid
# by UPI?") depend entirely on the earlier topic.
_SUBJECT_GROUPS = frozenset({
    "refund", "return", "exchange", "cancel", "damaged", "wrong", "missing", "nonreturnable", "discount",
    "inspection", "support", "pickup", "shipping_cost", "payment_failure",
})

_FOLLOWUP_CUES = re.compile(
    r"^(and\b|also\b|then\b|so\b|but\b|what about\b|how about\b|what if\b|what happens\b|how long\b|how much\b|"
    r"is it\b|does it\b|will it\b|can i\b|can we\b|do i\b|should i\b|why\b|when\b|which\b|where\b|who\b)",
    re.I,
)
_PRONOUNS = re.compile(r"\b(it|that|this|those|these|them|they|there|same|one)\b", re.I)
_BROAD_RE = re.compile(
    r"\b(what('?s| is| are)|tell me about|explain|describe|give me|can you (explain|tell|share)|overview|summar(y|ise|ize)"
    r"|how does)\b.*\b(polic(y|ies)|process|procedure|rules?|terms|conditions|guidelines|works?)\b",
    re.I,
)
_BARE_POLICY_RE = re.compile(r"^\s*(?:your\s+|the\s+)?(?:[\w'&-]+\s+){0,3}polic(?:y|ies)\??\s*$", re.I)


@dataclass
class QueryPlan:
    original: str
    standalone: str                       # conversation-resolved question (for dense search)
    lexical: str                          # standalone + vocabulary expansion (for keyword search)
    broad: bool
    topics: list[str] = field(default_factory=list)
    hint_terms: set[str] = field(default_factory=set)       # stemmed terms to match against section titles
    subject_terms: set[str] = field(default_factory=set)    # what the customer is asking about (full weight)
    qualifier_terms: set[str] = field(default_factory=set)  # how long / which payment method (half weight)
    resolved_from_history: bool = False


def _content_terms(text: str) -> list[str]:
    return retrieval_terms(text)


def is_followup(query: str) -> bool:
    q = query.strip()
    terms = _content_terms(q)
    if len(terms) <= 2:
        return True
    if len(q.split()) <= 8 and (_FOLLOWUP_CUES.match(q) and _PRONOUNS.search(q)):
        return True
    if re.match(r"^(what about|how about|and |what if)", q, re.I) and len(terms) <= 5:
        return True
    return bool(_PRONOUNS.search(q)) and len(terms) <= 4


def resolve_followup(query: str, history: list[str] | None, _depth: int = 0) -> tuple[str, bool]:
    """Combine a dependent follow-up with the previous customer question(s). `history` = earlier customer messages
    of THIS conversation, oldest first (the current message is not included)."""
    if not history or _depth > 2 or not is_followup(query):
        return query.strip(), False
    prev = history[-1].strip()
    prev_resolved, _ = resolve_followup(prev, history[:-1], _depth + 1)
    # The current message leads (it carries the new intent); the earlier topic follows as context.
    combined = f"{query.strip()} (regarding: {prev_resolved})"
    return combined[:500], True


def _expand(text: str, split: bool = False):
    """(topics, extra terms) -- or, with split=True, (topics, subject terms, qualifier terms)."""
    low = text.lower()
    topics, extra, subj, qual = [], [], [], []
    for name, (triggers, terms) in _GROUPS.items():
        if any(t in low for t in triggers):
            topics.append(name)
            added = [t for t in terms if t not in low]
            extra.extend(added)
            (subj if name in _SUBJECT_GROUPS else qual).extend(added)
    return (topics, subj, qual) if split else (topics, extra)


def understand(query: str, history: list[str] | None = None) -> QueryPlan:
    q = (query or "").strip()
    own_topics, _ = _expand(q)
    if _SUBJECT_GROUPS.intersection(own_topics) and len(_content_terms(q)) >= 2:
        standalone, resolved = q, False   # names its own subject: do not let earlier turns dilute the search
    else:
        standalone, resolved = resolve_followup(q, history)
    topics, subj_extra, qual_extra = _expand(standalone, split=True)
    extra = subj_extra + qual_extra
    lexical = standalone + (" " + " ".join(dict.fromkeys(extra)) if extra else "")

    content = _content_terms(q)
    broad = bool(_BROAD_RE.search(q) or _BARE_POLICY_RE.match(q)) and len(content) <= 6
    if broad and resolved:
        broad = False  # a follow-up about the earlier topic is, by definition, narrower

    hints = {stem(t) for t in _content_terms(lexical)}
    qual = {stem(t) for t in _content_terms(" ".join(qual_extra))}
    subject = {stem(t) for t in _content_terms(standalone + " " + " ".join(subj_extra))}
    qual -= subject
    return QueryPlan(
        original=q,
        standalone=standalone,
        lexical=lexical,
        broad=broad,
        topics=topics,
        hint_terms=hints,
        subject_terms=subject,
        qualifier_terms=qual,
        resolved_from_history=resolved,
    )
