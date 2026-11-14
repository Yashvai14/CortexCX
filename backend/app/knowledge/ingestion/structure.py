"""Document structure recovery: normalized text -> typed blocks with a heading hierarchy.

Extraction gives lines, not structure. This module recognises, line by line (not only at blank-line boundaries,
which many PDFs do not have):

  * chapter markers   "PAGE 4 - REFUND POLICY"      -> level-1 heading, number "4"
  * markdown headings "## Shipping"
  * numbered sections "4.1 General Refund Conditions" -> level = number of parts (4.1 -> 2, 4.1.2 -> 3)
  * lettered subheads "A. Innerwear"                 -> one level below the enclosing section
  * plain headings   "Shipping" (short Title-Case line directly above its paragraph)
  * lists            "- x", "1. x", "a) x"
  * tables           "| a | b |" rows (produced by the PDF/DOCX parsers)
  * paragraphs       everything else

The result is what the chunker packs and what citations are built from, so section numbers, titles and pages are
read from the document itself, never invented.
"""
import re
from dataclasses import dataclass, field

from app.knowledge.ingestion.normalize import PAGE_BREAK

_CHAPTER = re.compile(r"^PAGE\s+(\d{1,3})\s*[—–-]\s*(.+)$")
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_NUMBERED = re.compile(r"^(\d+(?:\.\d+)+)\s+(\S.{1,100})$")
_SINGLE_NUMBERED = re.compile(r"^(\d{1,2})[.)]\s+([A-Z][^.!?:;]{2,80})$")
_LETTERED = re.compile(r"^([A-Z])\.\s+([A-Z][^.!?:;]{2,70})$")
_LIST_ITEM = re.compile(r"^(?:[-*]\s+|\d{1,3}[.)]\s+|[A-Za-z][.)]\s+)")
# "Q9. How long does a refund take?" / "Question 3: ..." / "Scenario 2: Customer wants to return a shirt"
_ENTRY_Q = re.compile(r"^(Q\d{1,3}|Question\s+\d{1,3})\s*[.:)]\s*(.{4,200}[?])$", re.I)
_ENTRY_SCENARIO = re.compile(r"^(Scenario\s+\d{1,3})\s*[.:)]\s*(.{4,120})$", re.I)
_STEP_LABEL = re.compile(r"^(?:step|stage|phase)\s+\d+\b", re.I)


@dataclass
class Heading:
    level: int
    number: str | None
    title: str
    entry: bool = False   # an FAQ question / numbered scenario: one self-contained entry that gets its own chunk


@dataclass
class Block:
    kind: str                  # heading | para | list | table
    text: str
    page: int
    heading: Heading | None = None


@dataclass
class SectionPath:
    """Where a block sits: its own heading plus the chain of ancestors."""
    chain: list[Heading] = field(default_factory=list)

    @property
    def current(self) -> Heading | None:
        return self.chain[-1] if self.chain else None

    @property
    def parent(self) -> Heading | None:
        return self.chain[0] if len(self.chain) > 1 else None

    def label(self) -> str:
        return " > ".join(f"{h.number} {h.title}".strip() if h.number else h.title for h in self.chain)


def _title_case(s: str) -> str:
    small = {"and", "or", "of", "the", "a", "an", "to", "in", "for", "on", "at", "by", "with"}
    words = s.lower().split()
    return " ".join(w if (i and w in small) else w.capitalize() for i, w in enumerate(words))


def _is_plain_heading(line: str, prev_blank: bool, following: str | None) -> bool:
    """A short Title-Case / ALL-CAPS line that stands alone above its paragraph."""
    if not prev_blank or not following or len(line) > 70:
        return False
    if line[-1:] in ".,;:!?" or ":" in line or _STEP_LABEL.match(line) or _LIST_ITEM.match(line) or line.startswith("|"):
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) >= 4 and line.isupper():
        return True
    return (
        len(line.split()) <= 6
        and line[0].isupper()
        and len(following.strip()) > len(line) + 15
        and not following.lstrip().startswith(("|", "- "))
    )


def parse_blocks(text: str) -> list[Block]:
    blocks: list[Block] = []
    deepest_numbered = 0  # level of the most recent numbered section (for lettered subheads)

    for page_no, page in enumerate(text.split(PAGE_BREAK), start=1):
        lines = page.split("\n")
        i, n = 0, len(lines)
        para: list[str] = []
        lst: list[str] = []
        tbl: list[str] = []
        prev_blank = True

        def flush() -> None:
            nonlocal para, lst, tbl
            if para:
                blocks.append(Block("para", "\n".join(para), page_no))
            if lst:
                blocks.append(Block("list", "\n".join(lst), page_no))
            if tbl:
                blocks.append(Block("table", "\n".join(tbl), page_no))
            para, lst, tbl = [], [], []

        def next_line(k: int) -> str | None:
            for j in range(k + 1, n):
                if lines[j].strip():
                    return lines[j].strip()
            return None

        while i < n:
            raw = lines[i]
            line = raw.strip()
            if not line:
                flush()
                prev_blank = True
                i += 1
                continue

            heading: Heading | None = None
            m = _CHAPTER.match(line)
            if m and line.upper() == line:
                title = m.group(2).strip()
                nxt = next_line(i)
                # A long chapter title wraps onto a second ALL-CAPS line: consume it.
                if nxt and nxt.upper() == nxt and len(nxt) < 60 and not _NUMBERED.match(nxt) and not _CHAPTER.match(nxt):
                    title = f"{title} {nxt}"
                    j = i + 1
                    while j < n and lines[j].strip() != nxt:
                        j += 1
                    i = j
                heading = Heading(1, m.group(1), _title_case(title))
            elif (m := _MD_HEADING.match(line)):
                heading = Heading(len(m.group(1)), None, m.group(2).strip())
                nm = _NUMBERED.match(heading.title)
                if nm:
                    heading = Heading(len(nm.group(1).split(".")), nm.group(1), nm.group(2).strip())
            elif (m := _NUMBERED.match(line)) and line[-1] not in ".:;," and not _LIST_ITEM.match(line.split(" ", 1)[1]):
                heading = Heading(len(m.group(1).split(".")), m.group(1), m.group(2).strip())
            elif (m := _SINGLE_NUMBERED.match(line)) and prev_blank and len(m.group(2).split()) <= 8:
                nxt = next_line(i)
                if nxt and not re.match(r"^\d{1,3}[.)]\s", nxt):
                    heading = Heading(1, m.group(1), m.group(2).strip())
            elif (m := _ENTRY_Q.match(line) or _ENTRY_SCENARIO.match(line)):
                num = re.sub(r"\s+", " ", m.group(1)).strip()
                num = re.sub(r"(?i)^question ", "Q", num).rstrip(".:)")
                heading = Heading(max(deepest_numbered + 1, 3), num.title() if num.lower().startswith("scenario") else num.upper(),
                                  m.group(2).strip(), entry=True)
            elif (m := _LETTERED.match(line)) and deepest_numbered:
                nxt = next_line(i)
                if nxt and not _LETTERED.match(nxt):
                    heading = Heading(deepest_numbered + 1, m.group(1), m.group(2).strip())
            elif _is_plain_heading(line, prev_blank, next_line(i)):
                heading = Heading(1 if not deepest_numbered else deepest_numbered + 1, None,
                                  _title_case(line) if line.isupper() else line)

            if heading:
                if heading.title.isupper() and len(heading.title) > 3:
                    heading.title = _title_case(heading.title)
                flush()
                if heading.number and heading.number.replace(".", "").isdigit():
                    deepest_numbered = heading.level
                blocks.append(Block("heading", line, page_no, heading))
                prev_blank = False
                i += 1
                continue

            if line.startswith("|"):
                if para or lst:
                    flush()
                tbl.append(line)
            elif _LIST_ITEM.match(line) and not _STEP_LABEL.match(line):
                if para or tbl:
                    # a sentence ending in ":" belongs with the list it introduces
                    intro = para if (para and para[-1].rstrip().endswith(":")) else None
                    if intro is None:
                        flush()
                    else:
                        blocks.append(Block("para", "\n".join(para), page_no))
                        para = []
                        flush()
                lst.append(line)
            elif lst and not para:
                lst[-1] = lst[-1] + " " + line  # wrapped continuation of a list item
            else:
                if lst or tbl:
                    flush()
                para.append(line)
            prev_blank = False
            i += 1
        flush()
    return blocks
