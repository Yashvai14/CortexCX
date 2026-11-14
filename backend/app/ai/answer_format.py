"""Customer-facing answer formatting and safety checks.

The LLM (or the extractive fallback) produces Markdown. Before a customer sees it:
  * internal artefacts are removed: citation markers, "Passage [2]", "(Section 4.1)", "Page 4",
  * Markdown is repaired: lists on their own lines, blank lines between blocks, no run-on headings,
  * a reply cut off mid-sentence is trimmed to its last complete sentence,
  * replies that leak document extraction text or promise outcomes the policy does not guarantee are rejected so a
    safe, source-faithful fallback is used instead.
"""
import re

_CITATION = re.compile(r"[ \t]*(?:\[\d{1,2}\])+")
_SECTION_REF = re.compile(
    r"\s*[(\[]?\b(?:see\s+|per\s+|in\s+|under\s+)?(?:section|sec\.|§|clause|page|p\.)\s*\d+(?:\.\d+)*[)\]]?", re.I
)
_PASSAGE_REF = re.compile(r"\b(?:passage|source|excerpt)\s*\[?\d+\]?\s*[:.)-]?", re.I)
_BULLET_GLYPH = re.compile(r"(?m)^[ \t]*[•▪●◦‣∙·*][ \t]+")
_NUM_PAREN = re.compile(r"(?m)^([ \t]*)(\d{1,2})\)[ \t]+")
_LIST_LINE = re.compile(r"^\s*(?:[-*]\s+|\d{1,2}[.)]\s+)")
_INLINE_DASH_BULLETS = re.compile(r"\s+-\s+(?=[A-Z])")
_LEADERS = re.compile(r"^(?:answer|response|reply|assistant)\s*:\s*", re.I)

# Phrases that betray raw document text or the old template answer.
_ARTEFACTS = [
    re.compile(r"(?m)(?:^|[.:!?]\s)\d{1,2}\.\d{1,2}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,5}\s+(?=[A-Z][a-z]+\s)"),
    re.compile(r"\bPAGE\s+\d+\s*[—–-]", re.I),
    re.compile(r"does that answer your question\??\s*$", re.I),
    re.compile(r"NOT_IN_DOCUMENTS"),
    re.compile(r"\bPassage\s*[(\[]", re.I),
    re.compile(r"\bPassage\s*\d+", re.I),
    re.compile(r"\bpolicy record\b", re.I),                      # internal tool wording ("no official policy record")
    re.compile(r"\b\d{1,2}\.\d{1,2}\s+[A-Z][a-z]{2,}"),          # a raw section number + title in prose
]

# Outcomes only a human with the order in front of them may promise.
_PROMISES = [
    re.compile(r"\b(?:your|the)\s+(?:refund|return|exchange|replacement|cancell?ation)\s+(?:has been|is now|was|will be)\s+"
               r"(?:approved|processed|initiated|completed|confirmed|credited|issued|authori[sz]ed)\b", re.I),
    re.compile(r"\b(?:i|we)(?:'ve|\s+have|\s+will|'ll)\s+(?:approved|processed|initiated|issued|refunded|credited|cancell?ed|arranged)\b", re.I),
    re.compile(r"\b(?:guarantee[ds]?|definitely|for sure)\b[^.]{0,60}\b(?:refund|replacement|approval)\b", re.I),
    re.compile(r"\byour (?:money|payment) (?:has been|was|is) (?:refunded|returned|credited)\b", re.I),
]


def clean_answer(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    t = _LEADERS.sub("", t)
    t = _CITATION.sub("", t)
    t = _PASSAGE_REF.sub("", t)
    t = _SECTION_REF.sub("", t)
    t = re.sub(r"\s*[•▪●◦‣∙]\s+", "\n- ", t)      # inline "a • b • c" -> one bullet per line
    t = _BULLET_GLYPH.sub("- ", t)
    t = _NUM_PAREN.sub(r"\1\2. ", t)

    # a run of " - Item - Item - Item" on one line is a list that lost its line breaks
    out_lines: list[str] = []
    for line in t.split("\n"):
        if not line.lstrip().startswith("-") and len(_INLINE_DASH_BULLETS.findall(line)) >= 3:
            head, *items = _INLINE_DASH_BULLETS.split(line)
            if head.strip():
                out_lines.append(head.strip())
            out_lines.extend(f"- {i.strip()}" for i in items if i.strip())
        else:
            out_lines.append(line.rstrip())
    t = "\n".join(out_lines)

    # headings glued to the previous or next sentence
    t = re.sub(r"([^\n])\s*(#{1,3}\s+\S)", r"\1\n\n\2", t)
    t = re.sub(r"(?m)^(#{1,3}\s+[^\n]{1,80}?[.!?:])\s+(?=[A-Z])", r"\1\n\n", t)

    # blank line before/after list blocks and between paragraphs
    lines = t.split("\n")
    rebuilt: list[str] = []
    for i, line in enumerate(lines):
        is_list = bool(_LIST_LINE.match(line))
        prev = rebuilt[-1] if rebuilt else ""
        if rebuilt and prev.strip():
            prev_list = bool(_LIST_LINE.match(prev))
            if (is_list and not prev_list) or (not is_list and prev_list and line.strip() and not line.startswith(" ")):
                rebuilt.append("")
        rebuilt.append(line)
    t = "\n".join(rebuilt)

    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r" +([,.;:!?])", r"\1", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return trim_incomplete(t)


def trim_incomplete(text: str) -> str:
    """If generation stopped mid-sentence, drop the dangling fragment (keeps the answer ending on a full stop)."""
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return text
    last = lines[-1].rstrip()
    if _LIST_LINE.match(last) or re.search(r"[.!?:)\"'*`|]$", last):
        return "\n".join(lines).strip()
    cut = max(last.rfind(". "), last.rfind("? "), last.rfind("! "))
    if cut >= 0 and cut >= 0.4 * len(last):
        lines[-1] = last[: cut + 1]
    elif len(lines) > 1:
        lines.pop()  # the whole last line is a fragment
    return "\n".join(lines).strip()


def has_artefacts(text: str) -> bool:
    return any(rx.search(text) for rx in _ARTEFACTS)


_NEGATED_GUARANTEE = re.compile(r"\b(?:not|never|no|without)\b[^.]{0,40}\b(?:guarantee[ds]?|automatically)\b", re.I)


def has_unsupported_promise(text: str) -> bool:
    # "does NOT automatically guarantee a refund" restates a limit; it is the opposite of a promise.
    check = _NEGATED_GUARANTEE.sub("", text)
    return any(rx.search(check) for rx in _PROMISES)


# ── Faithful, readable fallback built only from the retrieved passages ─────────────────────────────

def _strip_heading(content: str, meta: dict | None = None) -> tuple[str, str]:
    """(heading line, body) of a chunk. The first line is the heading when it is the section's own "number title"."""
    first, _, rest = content.partition("\n")
    meta = meta or {}
    title = (meta.get("section_title") or meta.get("section") or "").lower()
    head = first.strip().lower()
    if rest and title and title in head and len(first) <= 160:
        return first.strip(), rest.strip()
    return "", content.strip()


def _blocks(body: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]


def _fit_block(block: str, budget: int) -> str | None:
    """A paragraph/list/table that fits whole is kept whole. One that does not is shortened at an item boundary and
    says so, never silently cut mid-list."""
    if len(block) <= budget:
        return block
    lines = block.split("\n")
    is_struct = lines[0].startswith(("-", "|")) or re.match(r"^\d{1,2}[.)]\s", lines[0])
    if not is_struct:
        sentences = re.split(r"(?<=[.!?])\s+", block)
        out, used = [], 0
        for sent in sentences:
            if used + len(sent) > budget and out:
                break
            out.append(sent)
            used += len(sent) + 1
        return " ".join(out)
    keep, used = [], 0
    for ln in lines:
        if used + len(ln) > budget and len(keep) >= 3:
            break
        keep.append(ln)
        used += len(ln) + 1
    if len(keep) < len(lines) and not lines[0].startswith("|"):
        keep.append("_...and more._")
    return "\n".join(x for x in keep if x)


def extractive_answer(chunks: list, broad: bool = False, max_chars: int = 1800) -> str | None:
    """Readable Markdown assembled from the retrieved passages themselves (used when the model is unavailable or its
    answer fails validation). Returns None when there is nothing to say."""
    if not chunks:
        return None
    parts: list[str] = []
    used = 0
    limit = 6 if broad else 2
    per_section = 520 if broad else 1100
    for chunk, _score in chunks[:limit]:
        meta = chunk.metadata_json or {}
        title = meta.get("section_title") or meta.get("section") or ""
        _, body = _strip_heading(chunk.content, meta)
        kept, spent = [], 0
        for blk in _blocks(body):
            fitted = _fit_block(blk, per_section - spent) if per_section - spent > 80 else None
            if not fitted:
                break
            kept.append(fitted)
            spent += len(fitted) + 2
        text = "\n\n".join(kept)
        block = (f"**{title}**\n\n" if title else "") + text
        if used and used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    if not parts:
        return None
    parent = ((chunks[0][0].metadata_json or {}).get("parent_section") or "").strip().lower()
    if broad and parent:
        intro = f"Here's an overview of our {parent if parent.endswith('policy') else parent + ' policy'}:"
    else:
        intro = "Here's what our policy says:"
    return f"{intro}\n\n" + "\n\n".join(parts)


# ── Polarity check: an invented "we do not ..." (or a dropped "not") is a policy error ─────────────
_NEG = re.compile(r"\b(?:not|no|never|cannot|can't|cant|won't|doesn't|don't|isn't|aren't|unable|without|neither|nor|non)")
_NEG = re.compile(_NEG.pattern + r"\b", re.I)
_LEAD_ANSWER = re.compile(r"^(?:no|yes|sure|certainly|unfortunately)[,.!]?\s+", re.I)


def _sentences(text: str) -> list[str]:
    out = []
    for line in re.split(r"\n+", text):
        line = re.sub(r"^\s*(?:[-*]|\d{1,2}[.)])\s+", "", line).strip()
        out.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if len(s.strip()) > 12)
    return out


def polarity_conflicts(answer: str, material: str) -> list[str]:
    """Answer sentences whose matching source sentences ALL say the opposite (negated vs not negated).

    A leading "No," / "Yes," answers the question and is not itself a claim, so it is ignored. If any closely
    matching source sentence agrees in polarity the sentence is fine (documents state rules and exceptions)."""
    from app.ai.text_utils import retrieval_terms, stem

    def terms(s: str) -> set[str]:
        return {stem(t) for t in retrieval_terms(s) if t not in {"not", "no", "never", "cannot"}}

    src = [(s, terms(s)) for s in _sentences(material)]
    bad = []
    for sent in _sentences(re.sub(r"\*\*", "", answer)):
        claim = _LEAD_ANSWER.sub("", sent)
        at = terms(claim)
        if len(at) < 4:
            continue
        scored = [(len(at & st) / len(at), s) for s, st in src]
        best_ov = max((o for o, _ in scored), default=0.0)
        if best_ov < 0.6:
            continue
        close = [s for o, s in scored if o >= max(0.6, best_ov - 0.1)]
        has_neg = bool(_NEG.search(claim))
        if all(bool(_NEG.search(s)) != has_neg for s in close):
            bad.append(sent)
    return bad


# ── Table consistency: a model may merge rows ("Card, UPI: 5-10 days") when the table gives different values ──
_RANGE = re.compile(r"\d+(?:\s*[–-]\s*\d+)?")


def _norm_range(r: str) -> str:
    return re.sub(r"\s+", "", r).replace("–", "-")


def table_conflicts(answer: str, material: str) -> list[str]:
    """Lines of the answer that attach a value to a table row label that the table gives a different value."""
    rows: dict[str, set[str]] = {}
    for line in material.split("\n"):
        if line.strip().startswith("|") and not re.match(r"^\s*\|[-| :]+\|?\s*$", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and len(cells[0]) >= 3:
                vals = {_norm_range(v) for v in _RANGE.findall(" ".join(cells[1:]))}
                if vals:
                    rows[cells[0].lower()] = vals
    bad = []
    for line in re.sub(r"\*\*", "", answer).split("\n"):
        low = line.lower()
        present = [lab for lab in rows if re.search(r"(?<!\w)" + re.escape(lab) + r"(?!\w)", low)]
        if not present:
            continue
        in_line = {_norm_range(v) for v in _RANGE.findall(line)}
        if not in_line:
            continue
        for lab in present:
            if not (rows[lab] & in_line) and len(in_line & set().union(*rows.values())) > 0:
                bad.append(line.strip())
                break
    return bad


def copy_ratio(answer: str, material: str, n: int = 6) -> float:
    """Share of the answer's n-word sequences that appear word-for-word in the source passages (1.0 = pasted)."""
    def grams(text: str) -> list[tuple[str, ...]]:
        words = re.findall(r"[a-z0-9']+", re.sub(r"[|*_#-]", " ", text.lower()))
        return [tuple(words[i:i + n]) for i in range(max(len(words) - n + 1, 0))]

    a = grams(answer)
    if not a:
        return 0.0
    m = set(grams(material))
    return sum(1 for g in a if g in m) / len(a)
