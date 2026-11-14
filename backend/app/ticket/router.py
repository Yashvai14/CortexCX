from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.auth.model import User
from app.auth.permissions import require_admin, require_agent
from app.customer.model import Customer
from app.database.session import get_db
from app.ticket.model import Ticket, TicketComment, TicketPriority, TicketStatus

router = APIRouter(prefix="/tickets", tags=["Tickets"])

# SLA: hours allowed to resolve, by priority
SLA_HOURS = {
    TicketPriority.URGENT: 4,
    TicketPriority.HIGH: 8,
    TicketPriority.MEDIUM: 24,
    TicketPriority.LOW: 72,
}
OPEN_STATUSES = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]


# ── Schemas ────────────────────────────────────────────────────────
class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=80)
    priority: TicketPriority = TicketPriority.MEDIUM
    customer_id: UUID | None = None
    conversation_id: UUID | None = None
    assignee_id: UUID | None = None


class TicketUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = None
    category: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: UUID | None = None
    unassign: bool = False


class CommentCreate(BaseModel):
    content: str = Field(min_length=1)
    is_internal: bool = False


# ── Helpers ────────────────────────────────────────────────────────
def _user_brief(u: User | None):
    return {"id": str(u.id), "full_name": u.full_name} if u else None


def _comment_out(c: TicketComment):
    return {
        "id": str(c.id),
        "ticket_id": str(c.ticket_id),
        "author": _user_brief(c.author),
        "content": c.content,
        "is_internal": c.is_internal,
        "is_event": c.is_event,
        "created_at": c.created_at,
    }


def _ticket_out(t: Ticket, with_comments: bool = False):
    now = datetime.now(timezone.utc)
    breached = bool(
        t.due_at and t.status in OPEN_STATUSES and t.due_at < now
    )
    out = {
        "id": str(t.id),
        "number": t.number,
        "reference": f"TCK-{t.number}",
        "subject": t.subject,
        "description": t.description,
        "category": t.category,
        "status": t.status.value,
        "priority": t.priority.value,
        "customer": (
            {"id": str(t.customer.id), "full_name": t.customer.full_name, "email": t.customer.email}
            if t.customer
            else None
        ),
        "conversation_id": str(t.conversation_id) if t.conversation_id else None,
        "assignee": _user_brief(t.assignee),
        "created_by": _user_brief(t.created_by),
        "due_at": t.due_at,
        "sla_breached": breached,
        "first_response_at": t.first_response_at,
        "resolved_at": t.resolved_at,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }
    if with_comments:
        out["comments"] = [_comment_out(c) for c in t.comments]
    return out


def _load(db: Session, user: User, ticket_id: UUID) -> Ticket:
    t = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.assignee),
            joinedload(Ticket.created_by),
            joinedload(Ticket.comments).joinedload(TicketComment.author),
        )
        .filter(Ticket.id == ticket_id, Ticket.workspace_id == user.workspace_id)
        .first()
    )
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return t


def _check_assignee(db: Session, user: User, assignee_id: UUID | None):
    if assignee_id is None:
        return
    ok = (
        db.query(User.id)
        .filter(User.id == assignee_id, User.workspace_id == user.workspace_id)
        .first()
    )
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Assignee is not in this workspace")


def _event(db: Session, ticket: Ticket, user: User, text: str):
    db.add(
        TicketComment(
            ticket_id=ticket.id,
            author_id=user.id,
            content=text,
            is_internal=True,
            is_event=True,
        )
    )


# ── Endpoints ──────────────────────────────────────────────────────
@router.get("/stats")
def ticket_stats(
    current_user: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    base = db.query(Ticket).filter(Ticket.workspace_id == current_user.workspace_id)
    counts = dict(
        base.with_entities(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    )
    now = datetime.now(timezone.utc)
    overdue = base.filter(Ticket.status.in_(OPEN_STATUSES), Ticket.due_at < now).count()
    unassigned = base.filter(
        Ticket.status.in_(OPEN_STATUSES), Ticket.assignee_id.is_(None)
    ).count()
    mine = base.filter(
        Ticket.status.in_(OPEN_STATUSES), Ticket.assignee_id == current_user.id
    ).count()
    return {
        "total": sum(counts.values()),
        "by_status": {s.value: counts.get(s, 0) for s in TicketStatus},
        "overdue": overdue,
        "unassigned": unassigned,
        "assigned_to_me": mine,
    }


@router.get("")
def list_tickets(
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    priority: TicketPriority | None = None,
    assignee_id: UUID | None = None,
    conversation_id: UUID | None = None,
    mine: bool = False,
    unassigned: bool = False,
    q: str | None = None,
    current_user: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Ticket)
        .options(joinedload(Ticket.customer), joinedload(Ticket.assignee), joinedload(Ticket.created_by))
        .filter(Ticket.workspace_id == current_user.workspace_id)
    )
    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if conversation_id:
        query = query.filter(Ticket.conversation_id == conversation_id)
    if mine:
        query = query.filter(Ticket.assignee_id == current_user.id)
    elif assignee_id:
        query = query.filter(Ticket.assignee_id == assignee_id)
    if unassigned:
        query = query.filter(Ticket.assignee_id.is_(None))
    if q:
        like = f"%{q.strip()}%"
        clauses = [Ticket.subject.ilike(like), Ticket.description.ilike(like)]
        digits = q.strip().upper().removeprefix("TCK-")
        if digits.isdigit():
            clauses.append(Ticket.number == int(digits))
        query = query.filter(or_(*clauses))

    tickets = query.order_by(Ticket.created_at.desc()).limit(500).all()
    return [_ticket_out(t) for t in tickets]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: TicketCreate,
    current_user: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    ws = current_user.workspace_id
    if data.customer_id:
        if not db.query(Customer.id).filter(
            Customer.id == data.customer_id, Customer.workspace_id == ws
        ).first():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Customer not found in this workspace")
    if data.conversation_id:
        from app.conversation.model import Conversation

        if not db.query(Conversation.id).filter(
            Conversation.id == data.conversation_id, Conversation.workspace_id == ws
        ).first():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Conversation not found in this workspace")
    _check_assignee(db, current_user, data.assignee_id)

    # Retry on the rare collision of concurrent number allocation
    for attempt in range(3):
        next_number = (
            db.query(func.coalesce(func.max(Ticket.number), 1000))
            .filter(Ticket.workspace_id == ws)
            .scalar()
            + 1
        )
        ticket = Ticket(
            workspace_id=ws,
            number=next_number,
            subject=data.subject.strip(),
            description=data.description,
            category=data.category,
            priority=data.priority,
            customer_id=data.customer_id,
            conversation_id=data.conversation_id,
            assignee_id=data.assignee_id,
            created_by_id=current_user.id,
            due_at=datetime.now(timezone.utc) + timedelta(hours=SLA_HOURS[data.priority]),
        )
        db.add(ticket)
        try:
            db.flush()
            break
        except Exception:
            db.rollback()
            if attempt == 2:
                raise HTTPException(status.HTTP_409_CONFLICT, "Could not allocate ticket number")
    _event(db, ticket, current_user, f"{current_user.full_name} created this ticket")
    db.commit()
    return _ticket_out(_load(db, current_user, ticket.id), with_comments=True)


@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: UUID,
    current_user: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    return _ticket_out(_load(db, current_user, ticket_id), with_comments=True)


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: UUID,
    data: TicketUpdate,
    current_user: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    t = _load(db, current_user, ticket_id)
    who = current_user.full_name

    if data.subject is not None:
        t.subject = data.subject.strip()
    if data.description is not None:
        t.description = data.description
    if data.category is not None:
        t.category = data.category or None

    if data.priority is not None and data.priority != t.priority:
        _event(db, t, current_user, f"{who} changed priority from {t.priority.value} to {data.priority.value}")
        t.priority = data.priority
        if t.status in OPEN_STATUSES:
            t.due_at = t.created_at + timedelta(hours=SLA_HOURS[data.priority])

    if data.unassign and t.assignee_id:
        _event(db, t, current_user, f"{who} unassigned this ticket")
        t.assignee_id = None
    elif data.assignee_id is not None and data.assignee_id != t.assignee_id:
        _check_assignee(db, current_user, data.assignee_id)
        assignee = db.get(User, data.assignee_id)
        _event(db, t, current_user, f"{who} assigned this ticket to {assignee.full_name}")
        t.assignee_id = data.assignee_id
        if t.status == TicketStatus.OPEN:
            t.status = TicketStatus.IN_PROGRESS

    if data.status is not None and data.status != t.status:
        _event(db, t, current_user, f"{who} changed status from {t.status.value} to {data.status.value}")
        t.status = data.status
        if data.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            t.resolved_at = t.resolved_at or datetime.now(timezone.utc)
        else:
            t.resolved_at = None

    db.commit()
    return _ticket_out(_load(db, current_user, ticket_id), with_comments=True)


@router.post("/{ticket_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(
    ticket_id: UUID,
    data: CommentCreate,
    current_user: User = Depends(require_agent),
    db: Session = Depends(get_db),
):
    t = _load(db, current_user, ticket_id)
    comment = TicketComment(
        ticket_id=t.id,
        author_id=current_user.id,
        content=data.content.strip(),
        is_internal=data.is_internal,
    )
    db.add(comment)
    if not data.is_internal and t.first_response_at is None:
        t.first_response_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    t = _load(db, current_user, ticket_id)
    db.delete(t)
    db.commit()
