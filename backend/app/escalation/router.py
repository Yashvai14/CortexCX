from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.model import User, UserRole
from app.auth.permissions import require_roles
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.model import Conversation
from app.database.session import get_db
from app.escalation.model import EscalationStatus, HumanEscalation
from app.learning.model import AgentFeedback
from app.memory.service import CustomerMemoryService

router = APIRouter(
    prefix="/escalations",
    tags=["Human Handoff & Agent Assist"],
)


class AgentRespondRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Agent response message to send to customer")
    resolve: bool = Field(default=False, description="Whether to mark the escalation as resolved after sending")


class FeedbackRequest(BaseModel):
    conversation_id: UUID
    message_id: UUID | None = None
    original_response: str
    corrected_response: str
    reason: str | None = None


@router.get("")
def list_escalations(
    status_filter: EscalationStatus | None = None,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)),
    db: Session = Depends(get_db),
):
    """List escalations requiring human agent intervention."""
    q = db.query(HumanEscalation).filter(HumanEscalation.workspace_id == current_user.workspace_id)
    if status_filter:
        q = q.filter(HumanEscalation.status == status_filter)
    else:
        q = q.filter(HumanEscalation.status.in_([EscalationStatus.PENDING, EscalationStatus.IN_PROGRESS]))

    escalations = q.order_by(HumanEscalation.created_at.desc()).all()
    results = []
    for esc in escalations:
        results.append({
            "id": str(esc.id),
            "conversation_id": str(esc.conversation_id),
            "customer_id": str(esc.customer_id),
            "customer_name": esc.customer.full_name if esc.customer else "Unknown",
            "customer_email": esc.customer.email if esc.customer else None,
            "status": esc.status.value if hasattr(esc.status, "value") else str(esc.status),
            "reason": esc.reason,
            "confidence_score": esc.confidence_score,
            "summary": esc.summary,
            "suggested_reply": esc.suggested_reply,
            "assigned_agent_name": esc.assigned_agent.full_name if esc.assigned_agent else None,
            "created_at": esc.created_at.isoformat() if esc.created_at else None,
        })
    return results


@router.get("/{id}")
def get_escalation_detail(
    id: UUID,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)),
    db: Session = Depends(get_db),
):
    """Get rich Agent Assist context for an escalated conversation."""
    esc = (
        db.query(HumanEscalation)
        .filter(
            HumanEscalation.id == id,
            HumanEscalation.workspace_id == current_user.workspace_id,
        )
        .first()
    )
    if not esc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")

    conversation = db.query(Conversation).filter(Conversation.id == esc.conversation_id).first()
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == esc.conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    memories = CustomerMemoryService.get_relevant_memories(
        db=db,
        workspace_id=current_user.workspace_id,
        customer_id=esc.customer_id,
        limit=5,
    )

    return {
        "id": str(esc.id),
        "conversation_id": str(esc.conversation_id),
        "conversation_subject": conversation.subject if conversation else "",
        "customer": {
            "id": str(esc.customer.id) if esc.customer else None,
            "name": esc.customer.full_name if esc.customer else "",
            "email": esc.customer.email if esc.customer else "",
            "phone": esc.customer.phone if esc.customer else None,
            "company": esc.customer.company_name if esc.customer else None,
        },
        "status": esc.status.value if hasattr(esc.status, "value") else str(esc.status),
        "reason": esc.reason,
        "confidence_score": esc.confidence_score,
        "summary": esc.summary,
        "suggested_reply": esc.suggested_reply,
        "customer_memories": memories,
        "messages": [
            {
                "id": str(m.id),
                "sender_type": m.sender_type.value if hasattr(m.sender_type, "value") else str(m.sender_type),
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post("/{id}/claim")
def claim_escalation(
    id: UUID,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)),
    db: Session = Depends(get_db),
):
    """Assign this escalation to the logged-in support agent."""
    esc = (
        db.query(HumanEscalation)
        .filter(
            HumanEscalation.id == id,
            HumanEscalation.workspace_id == current_user.workspace_id,
        )
        .first()
    )
    if not esc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")

    esc.assigned_agent_id = current_user.id
    esc.status = EscalationStatus.IN_PROGRESS

    conv = db.query(Conversation).filter(Conversation.id == esc.conversation_id).first()
    if conv:
        conv.ai_enabled = False
        conv.ai_state = "escalated"

    db.commit()
    return {"message": "Escalation claimed successfully", "status": esc.status.value}


@router.post("/{id}/respond")
def respond_to_escalation(
    id: UUID,
    data: AgentRespondRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)),
    db: Session = Depends(get_db),
):
    """Send an agent response to the customer in the escalated conversation."""
    esc = (
        db.query(HumanEscalation)
        .filter(
            HumanEscalation.id == id,
            HumanEscalation.workspace_id == current_user.workspace_id,
        )
        .first()
    )
    if not esc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")

    msg = Message(
        conversation_id=esc.conversation_id,
        sender_type=MessageSenderType.AGENT,
        sender_user_id=current_user.id,
        content=data.content.strip(),
    )
    db.add(msg)

    if data.resolve:
        esc.status = EscalationStatus.RESOLVED
        esc.resolved_at = datetime.utcnow()
        conv = db.query(Conversation).filter(Conversation.id == esc.conversation_id).first()
        if conv:
            conv.ai_enabled = True
            conv.ai_state = "idle"

    db.commit()
    db.refresh(msg)
    return {"message": "Agent reply sent successfully", "message_id": str(msg.id)}



@router.post("/{id}/return-to-ai")
def return_conversation_to_ai(
    id: UUID,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)),
    db: Session = Depends(get_db),
):
    """Return control of an escalated conversation back to the AI engine."""
    esc = (
        db.query(HumanEscalation)
        .filter(
            HumanEscalation.id == id,
            HumanEscalation.workspace_id == current_user.workspace_id,
        )
        .first()
    )
    if not esc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")

    conv = db.query(Conversation).filter(Conversation.id == esc.conversation_id).first()
    if conv:
        conv.ai_enabled = True
        conv.ai_state = "idle"

    esc.status = EscalationStatus.RETURNED_TO_AI
    esc.resolved_at = datetime.utcnow()
    db.commit()
    return {"message": "Conversation returned to AI engine successfully"}


@router.post("/feedback")
def submit_agent_feedback(
    data: FeedbackRequest,
    current_user: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.AGENT)),
    db: Session = Depends(get_db),
):
    """Submit agent correction to AI response for learning engine dataset capture."""
    feedback = AgentFeedback(
        workspace_id=current_user.workspace_id,
        conversation_id=data.conversation_id,
        message_id=data.message_id,
        agent_id=current_user.id,
        original_response=data.original_response,
        corrected_response=data.corrected_response,
        reason=data.reason,
        is_verified=True,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"message": "Feedback captured for continuous learning", "feedback_id": str(feedback.id)}
