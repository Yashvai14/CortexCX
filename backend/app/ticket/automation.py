"""Keeps a support Ticket in step with a human escalation and its conversation.

Lifecycle (driven by hooks in the AI orchestrator and the escalation router):
  AI escalates          -> ticket auto-created (OPEN)
  agent claims          -> IN_PROGRESS, assigned to that agent
  agent replies         -> WAITING (on the customer)
  customer writes again -> IN_PROGRESS
  agent clicks resolve  -> customer is ASKED first ("Is your issue resolved?" + suggested answers)
  customer says yes     -> RESOLVED, conversation returns to the AI
  customer says no      -> IN_PROGRESS, stays with the agent
  returned to AI        -> RESOLVED
"""
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ticket.model import Ticket, TicketComment, TicketPriority, TicketStatus

OPEN_STATUSES = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]
SLA_HOURS = {
    TicketPriority.URGENT: 4,
    TicketPriority.HIGH: 8,
    TicketPriority.MEDIUM: 24,
    TicketPriority.LOW: 72,
}

AWAITING_CONFIRMATION = "awaiting_confirmation"
CONFIRM_PROMPT = "My teammate thinks your issue is sorted now. Is that right?"
def confirm_prompt(first_name: str = "") -> str:
    who = f"{first_name}, " if first_name else ""
    return f"{who}my teammate thinks your issue is sorted now. Is that right?"


CONFIRM_YES = "Yes, it's resolved"
CONFIRM_NO = "No, I still need help"
CONFIRM_SUGGESTIONS = [CONFIRM_YES, CONFIRM_NO]

_URGENT_WORDS = re.compile(r"\b(urgent|legal|lawyer|fraud|chargeback|angry|furious|unacceptable|immediately)\b", re.I)
_YES = re.compile(r"\b(yes|yep|yeah|yup|resolved|solved|fixed|sorted|all good|thanks|thank you|works now)\b", re.I)
_NO = re.compile(r"\b(no|nope|not|still|isn'?t|didn'?t|doesn'?t|unresolved|again|problem)\b", re.I)


def classify_confirmation(text: str) -> str:
    """Return 'yes', 'no' or 'unclear' for the customer's reply to the resolution question."""
    t = (text or "").strip()
    if t == CONFIRM_YES:
        return "yes"
    if t == CONFIRM_NO:
        return "no"
    no, yes = bool(_NO.search(t)), bool(_YES.search(t))
    if no and not yes:
        return "no"
    if yes and not no:
        return "yes"
    return "unclear"


def _event(db: Session, ticket: Ticket, text: str) -> None:
    db.add(TicketComment(ticket_id=ticket.id, author_id=None, content=text, is_internal=True, is_event=True))


def active_ticket(db: Session, conversation_id: UUID) -> Ticket | None:
    return (
        db.query(Ticket)
        .filter(Ticket.conversation_id == conversation_id, Ticket.status.in_(OPEN_STATUSES))
        .order_by(Ticket.created_at.desc())
        .first()
    )


def create_for_escalation(db: Session, esc, conversation) -> Ticket:
    """Create (or reuse) the ticket for an escalation. Caller commits."""
    existing = active_ticket(db, conversation.id)
    if existing:
        return existing

    priority = TicketPriority.URGENT if _URGENT_WORDS.search(f"{esc.reason} {conversation.subject or ''}") else TicketPriority.HIGH
    ws = esc.workspace_id
    number = (
        db.query(func.coalesce(func.max(Ticket.number), 1000)).filter(Ticket.workspace_id == ws).scalar() + 1
    )
    ticket = Ticket(
        workspace_id=ws,
        number=number,
        subject=(conversation.subject or "Customer needs human support")[:255],
        description=f"Escalation reason: {esc.reason}\n\n{esc.summary or ''}".strip(),
        category="Escalation",
        priority=priority,
        status=TicketStatus.OPEN,
        customer_id=esc.customer_id,
        conversation_id=conversation.id,
        due_at=datetime.now(timezone.utc) + timedelta(hours=SLA_HOURS[priority]),
    )
    db.add(ticket)
    db.flush()
    _event(db, ticket, f"Ticket auto-created from AI escalation ({esc.reason})")
    return ticket


def sync(
    db: Session,
    conversation_id: UUID,
    status: TicketStatus | None = None,
    note: str | None = None,
    assignee_id: UUID | None = None,
    agent_replied: bool = False,
) -> Ticket | None:
    """Move the conversation's open ticket to a new status, logging why. Caller commits."""
    t = active_ticket(db, conversation_id)
    if not t:
        return None
    if assignee_id and t.assignee_id != assignee_id:
        t.assignee_id = assignee_id
    if agent_replied and t.first_response_at is None:
        t.first_response_at = datetime.now(timezone.utc)
    changed = bool(status and status != t.status)
    if changed:
        t.status = status
        if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            t.resolved_at = datetime.now(timezone.utc)
    if note and (changed or status is None):
        _event(db, t, note)
    return t
