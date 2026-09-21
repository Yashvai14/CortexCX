from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.knowledge.model import DocumentChunk


class BaseRetriever(ABC):
    """Abstract interface for knowledge chunk retrievers."""

    @abstractmethod
    def retrieve(
        self,
        db: Session,
        workspace_id: UUID,
        query: str,
        top_k: int = 5,
        knowledge_source_id: UUID | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Retrieve top_k (chunk, score) tuples for query strictly within the workspace."""
        pass
