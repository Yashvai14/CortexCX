from app.core.config import settings
import uuid
import app.database.models
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.knowledge.model import Document, DocumentChunk, KnowledgeSource, KnowledgeSourceType
from app.memory.service import CustomerMemoryService
from app.rag.bm25_retriever import BM25Retriever
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.retrieval import RAGRetriever
from app.workspace.model import Workspace
from app.customer.model import Customer, CustomerStatus


def test_customer_memory_extraction_and_retrieval():
    db: Session = SessionLocal()
    try:
        ws_id = uuid.uuid4()
        ws = Workspace(id=ws_id, name=f"WS {ws_id.hex[:6]}", slug=f"ws-{ws_id.hex[:6]}")
        db.add(ws)

        cust = Customer(
            workspace_id=ws_id,
            full_name="Alice Green",
            email=f"alice_{ws_id.hex[:6]}@example.com",
            status=CustomerStatus.ACTIVE,
        )
        db.add(cust)
        db.commit()

        # 1. Test episodic memory extraction from text
        message = "Hi! I am allergic to peanuts and I prefer vegetarian products. Also please leave at the front porch."
        extracted = CustomerMemoryService.process_and_persist_extracted_memories(
            db=db,
            workspace_id=ws_id,
            customer_id=cust.id,
            customer_message=message,
        )
        assert len(extracted) >= 2

        # 2. Test memory retrieval by relevance
        memories = CustomerMemoryService.get_relevant_memories(
            db=db,
            workspace_id=ws_id,
            customer_id=cust.id,
            query="Can I eat this peanut snack?",
        )
        assert len(memories) >= 1
        assert any("peanut" in m.lower() for m in memories)
    finally:
        db.close()


def test_hybrid_rag_dense_and_bm25_retrieval():
    db: Session = SessionLocal()
    try:
        ws_id = uuid.uuid4()
        ws = Workspace(id=ws_id, name=f"WS {ws_id.hex[:6]}", slug=f"ws-{ws_id.hex[:6]}")
        db.add(ws)

        ks = KnowledgeSource(
            workspace_id=ws_id,
            name="Store FAQ",
            source_type=KnowledgeSourceType.TXT,
        )
        db.add(ks)
        db.flush()

        doc = Document(
            workspace_id=ws_id,
            knowledge_source_id=ks.id,
            title="Shipping & Returns Policy",
            content="Full document text",
        )
        db.add(doc)
        db.flush()

        # Create chunks
        chunk1 = DocumentChunk(
            workspace_id=ws_id,
            document_id=doc.id,
            chunk_index=0,
            content="Standard delivery takes 3 to 5 business days via FedEx or UPS Ground.",
            embedding=[0.1] * settings.EMBEDDING_DIMENSION,
        )
        chunk2 = DocumentChunk(
            workspace_id=ws_id,
            document_id=doc.id,
            chunk_index=1,
            content="Returns must be postmarked within 30 days of purchase for a full refund.",
            embedding=[0.2] * settings.EMBEDDING_DIMENSION,
        )
        chunk3 = DocumentChunk(
            workspace_id=ws_id,
            document_id=doc.id,
            chunk_index=2,
            content="All customer accounts get free gift wrapping on anniversary orders.",
            embedding=[0.3] * settings.EMBEDDING_DIMENSION,
        )
        db.add_all([chunk1, chunk2, chunk3])
        db.commit()

        # 1. Test BM25 keyword retrieval
        bm25 = BM25Retriever()
        results_bm25 = bm25.retrieve(
            db=db,
            workspace_id=ws_id,
            query="FedEx delivery days",
            top_k=2,
        )
        assert len(results_bm25) >= 1
        assert "FedEx" in results_bm25[0][0].content

        # 2. Test Full Hybrid RAG retrieval pipeline (BM25 + Dense + Reranking + Compression)
        retriever = RAGRetriever()
        hybrid_results = retriever.retrieve(
            db=db,
            workspace_id=ws_id,
            query="How many days do I have to return for refund?",
            top_k=2,
        )
        assert len(hybrid_results) >= 1
        assert "30 days" in hybrid_results[0][0].content
    finally:
        db.close()
