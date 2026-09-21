from abc import ABC, abstractmethod
from uuid import UUID
from sqlalchemy.orm import Session

from app.channels.schema import ChannelIncomingMessage, ChannelResponse


class BaseChannelAdapter(ABC):
    """Abstract interface for omnichannel customer communication adapters."""

    @abstractmethod
    def handle_incoming_message(
        self,
        db: Session,
        workspace_id: UUID,
        incoming: ChannelIncomingMessage,
    ) -> ChannelResponse:
        pass
