import re

STOPWORDS = frozenset(
    """a an the and or but if then so of to in on at by for with from into about as is are was were be been being
    am do does did done have has had having can could would should will shall may might must i me my mine we our ours
    you your yours he she it its they them their this that these those there here what which who whom whose when where
    why how not no yes please pls hi hello hey thanks thank any some got get give gave tell show want need like just
    also very much more most can't cant dont don't im i'm ive i've ill i'll id i'd never ever always came come comes stock available availability
    buy looking look find search price cost much many order orders item items product products one ones
    """.split()
)

# Matches real order references: ORD-1001, #1001, order 1001, A12345 ... must contain a digit
ORDER_REF_RE = re.compile(
    r"(?:\border\s*(?:number|no\.?|id|#)?\s*:?\s*#?\s*|#)([A-Za-z]{0,5}-?\d{3,12})\b"
    r"|\b([A-Za-z]{2,5}-\d{3,12})\b",
    re.IGNORECASE,
)


def extract_order_number(text: str) -> str | None:
    m = ORDER_REF_RE.search(text)
    if not m:
        return None
    return (m.group(1) or m.group(2)).upper()


def keywords(text: str, max_terms: int = 6) -> list[str]:
    """Informative lowercase terms of a message (stopwords removed, de-duplicated, order preserved)."""
    seen: list[str] = []
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", text.lower()):
        tok = tok.strip("'-")
        if len(tok) < 3 or tok in STOPWORDS or tok in seen:
            continue
        seen.append(tok)
    return seen[:max_terms]


def stem(term: str) -> str:
    """Very light stemmer so 'hoodies' matches 'hoodie' and 'returned' matches 'return'."""
    for suffix in ("ies", "ing", "ed", "es", "s"):
        if term.endswith(suffix) and len(term) - len(suffix) >= 3:
            return term[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return term


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[.][A-Za-z]{2,}")


def extract_emails(*texts: str) -> list[str]:
    """Lower-cased, de-duplicated email addresses mentioned in the given texts."""
    found: list[str] = []
    for t in texts:
        for m in EMAIL_RE.findall(t or ""):
            m = m.lower()
            if m not in found:
                found.append(m)
    return found


# Standard English function words only. Unlike STOPWORDS (tuned for reading customer intents), this list keeps
# domain words such as "order", "price", "stock" because they are meaningful when searching documents.
GENERAL_STOPWORDS = frozenset(
    """a an the and or but if then so of to in on at by for with from into about as is are was were be been being
    am do does did done have has had having can could would should will shall may might must i me my mine we our ours
    you your yours he she it its they them their this that these those there here what which who whom whose when where
    why how not no yes any some than too very just also please s t""".split()
)


def retrieval_terms(text: str) -> list[str]:
    """Stemmed content words of `text`, for lexical matching against document passages."""
    import re as _re

    return [stem(t) for t in _re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower()) if t not in GENERAL_STOPWORDS]


# So common in business documents that matching them says nothing about relevance ("who founded the company?").
_COVERAGE_STOP = frozenset(stem(w) for w in (
    "company customer customers store business please thank thanks help need want know tell information detail details "
    "regarding question questions".split()))


def lexical_coverage(query: str, passage: str) -> float:
    """Fraction of the query's distinct content words that appear (stemmed) in the passage, 0..1."""
    q = set(retrieval_terms(query)) - _COVERAGE_STOP
    if not q:
        return 0.0
    return len(q & set(retrieval_terms(passage))) / len(q)
