import re
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.memory.model import CustomerMemory


class CustomerMemoryService:
    """Manages channel-independent short-term, episodic, and long-term customer memory."""

    @staticmethod
    def save_memory(
        db: Session,
        workspace_id: UUID,
        customer_id: UUID,
        content: str,
        memory_type: str = "preference",
        confidence: float = 1.0,
        source_conversation_id: UUID | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> CustomerMemory:
        clean_content = content.strip()
        # Avoid duplicate identical active memories for this customer
        existing = (
            db.query(CustomerMemory)
            .filter(
                CustomerMemory.workspace_id == workspace_id,
                CustomerMemory.customer_id == customer_id,
                CustomerMemory.content == clean_content,
                CustomerMemory.is_active.is_(True),
            )
            .first()
        )
        if existing:
            return existing

        memory = CustomerMemory(
            workspace_id=workspace_id,
            customer_id=customer_id,
            memory_type=memory_type,
            content=clean_content,
            confidence=confidence,
            source_conversation_id=source_conversation_id,
            metadata_json=metadata_json,
            is_active=True,
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return memory

    @staticmethod
    def get_relevant_memories(
        db: Session,
        workspace_id: UUID,
        customer_id: UUID,
        query: str | None = None,
        limit: int = 5,
    ) -> list[str]:
        """Retrieve active customer memories relevant to the workspace, customer, and query."""
        all_memories = (
            db.query(CustomerMemory)
            .filter(
                CustomerMemory.workspace_id == workspace_id,
                CustomerMemory.customer_id == customer_id,
                CustomerMemory.is_active.is_(True),
            )
            .order_by(CustomerMemory.created_at.desc())
            .all()
        )

        if not all_memories:
            return []

        if not query or not query.strip():
            return [m.content for m in all_memories[:limit]]

        query_terms = set(re.findall(r"\w+", query.lower()))
        scored: list[tuple[str, int]] = []
        for mem in all_memories:
            mem_terms = set(re.findall(r"\w+", mem.content.lower()))
            overlap = len(query_terms.intersection(mem_terms))
            scored.append((mem.content, overlap))

        # Sort by relevance overlap descending, then take top limit
        scored.sort(key=lambda x: x[1], reverse=True)
        return [content for content, _ in scored[:limit]]

    @staticmethod
    def extract_memories_from_text(
        text: str,
    ) -> list[tuple[str, str]]:
        """Heuristic rule-based episodic fact extractor from customer dialogue turns.
        Returns list of (content, memory_type).
        """
        extracted: list[tuple[str, str]] = []
        lower = text.lower()

        # Preference patterns: "I prefer X", "I like X", "I love X", "I always buy X"
        pref_matches = re.findall(r"(?:i\s+prefer|i\s+like|i\s+love|i\s+always\s+use|i\s+usually\s+buy)\s+([^,.;!?]+)", lower)
        for p in pref_matches:
            clean_p = p.strip()
            if len(clean_p) > 3 and clean_p not in ["it", "this", "that", "to"]:
                extracted.append((f"Customer prefers: {clean_p}", "preference"))

        # Dietary / Material / Allergy: "I am allergic to X", "vegetarian", "vegan", "sensitive to"
        allergy_match = re.findall(r"(?:i\s+am\s+allergic\s+to|allergic\s+to|sensitive\s+to)\s+([^,.;!?]+)", lower)
        for a in allergy_match:
            extracted.append((f"Customer is sensitive/allergic to: {a.strip()}", "allergy"))

        if "vegetarian" in lower:
            extracted.append(("Customer prefers vegetarian products.", "preference"))
        if "vegan" in lower:
            extracted.append(("Customer prefers vegan products.", "preference"))

        # Delivery note: "please leave at X", "deliver to X"
        delivery_match = re.findall(r"(?:leave\s+(?:it\s+)?at|deliver\s+to)\s+([^,.;!?]+)", lower)
        for d in delivery_match:
            extracted.append((f"Delivery instruction: leave at {d.strip()}", "delivery_instruction"))

        # Sizing note: "I wear size X", "my size is X"
        size_match = re.findall(r"(?:i\s+wear\s+size|my\s+size\s+is)\s+([a-zA-Z0-9]+)", lower)
        for s in size_match:
            extracted.append((f"Customer sizing: {s.strip().upper()}", "sizing"))

        return extracted

    @classmethod
    def process_and_persist_extracted_memories(
        cls,
        db: Session,
        workspace_id: UUID,
        customer_id: UUID,
        customer_message: str,
        conversation_id: UUID | None = None,
    ) -> list[str]:
        items = cls.extract_memories_from_text(customer_message)
        persisted = []
        for content, mem_type in items:
            mem = cls.save_memory(
                db=db,
                workspace_id=workspace_id,
                customer_id=customer_id,
                content=content,
                memory_type=mem_type,
                source_conversation_id=conversation_id,
            )
            persisted.append(mem.content)
        return persisted
