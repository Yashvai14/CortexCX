"""Document ingestion: extract -> normalize -> chunk -> embed -> store (pgvector).

Extraction happens in the parsers. This module owns everything after it:

    build_chunks()          normalize + chunk + persist chunk rows (fast, synchronous)
    embed_document()        embed chunks with the configured model and store vectors (slow, can run in background)
    run_embedding_job()     background entry point with its own DB session; records FAILED + the reason on error
    reindex_document()      rebuild chunks from stored content and re-embed (used by /knowledge/reindex)
"""
import re
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.embeddings.factory import get_embedding_provider
from app.knowledge.ingestion.chunker import chunk_document
from app.knowledge.ingestion.normalize import normalize_text
from app.knowledge.model import Document, DocumentChunk, DocumentStatus


def embedding_input(doc_title: str, section: str | None, content: str, section_path: str | None = None) -> str:
    """Text actually embedded: the chunk prefixed with its document title and section path.

    Chunks lose context once separated ("30 days" of what?). Prefixing restores it for retrieval while the stored
    `content` shown to the LLM and user stays the clean passage.
    """
    where = section_path or section
    head = doc_title if not where or where.lower() == doc_title.lower() else f"{doc_title} - {where}"
    return f"{head}\n{content}"


_VERSION_RE = re.compile(r"document\s+version\s*[:\-]?\s*(?:\n\s*)?([\w.\-]+)", re.I)
_EFFECTIVE_RE = re.compile(r"effective\s+date\s*[:\-]?\s*(?:\n\s*)?([^\n]{3,40})", re.I)
_UPDATED_RE = re.compile(r"last\s+updated\s*[:\-]?\s*(?:\n\s*)?([^\n]{3,40})", re.I)


def extract_document_facts(text: str) -> dict:
    """Version / dates exactly as printed in the document's first page (nothing is inferred)."""
    head = text[:3000]
    facts = {}
    for key, rx in (("document_version", _VERSION_RE), ("effective_date", _EFFECTIVE_RE), ("last_updated", _UPDATED_RE)):
        m = rx.search(head)
        if m:
            facts[key] = m.group(1).strip()
    return facts


def build_chunks(db: Session, document: Document) -> list[DocumentChunk]:
    """Normalize the document text and (re)create its chunk rows, without embeddings."""
    normalized = normalize_text(document.content)
    if not normalized:
        raise ValueError("Document has no extractable text after normalization")

    specs = chunk_document(normalized, document_title=document.title)
    if not specs:
        raise ValueError("Document produced zero chunks")

    facts = extract_document_facts(normalized)
    if facts:
        document.metadata_json = {**(document.metadata_json or {}), **facts}
    doc_name = document.filename or document.title
    version = (document.metadata_json or {}).get("document_version")

    document.content = normalized
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete(synchronize_session=False)
    chunks = [
        DocumentChunk(
            workspace_id=document.workspace_id,
            document_id=document.id,
            chunk_index=i,
            content=spec.content,
            metadata_json={
                **spec.metadata,
                "chunk_size": len(spec.content),
                "chunk_index": i,
                "document_id": str(document.id),
                "document_name": doc_name,
                "document_version": version,
            },
        )
        for i, spec in enumerate(specs)
    ]
    db.add_all(chunks)
    document.status = DocumentStatus.PROCESSING
    document.error_message = None
    db.flush()
    return chunks


def embed_document(db: Session, document: Document) -> int:
    """Embed every chunk of `document` and store the vectors. Returns the number of chunks embedded."""
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    if not chunks:
        raise ValueError("Document has no chunks to embed")

    provider = get_embedding_provider()
    texts = [
        embedding_input(
            document.title,
            (c.metadata_json or {}).get("section"),
            c.content,
            (c.metadata_json or {}).get("section_path"),
        )
        for c in chunks
    ]
    vectors = provider.embed_documents(texts)
    model = getattr(provider, "model_name", "unknown")
    for chunk, vec in zip(chunks, vectors):
        chunk.embedding = vec
        chunk.embedding_model = model

    document.status = DocumentStatus.COMPLETED
    document.error_message = None
    db.commit()
    return len(chunks)


def run_embedding_job(document_id: UUID) -> None:
    """Background task: embed a document that has already been chunked. Never raises."""
    from app.database.database import SessionLocal

    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            return
        try:
            n = embed_document(db, document)
            logger.info(f"Embedded {n} chunks for document {document_id}")
        except Exception as e:  # surface the reason in the UI instead of leaving it "processing" forever
            db.rollback()
            document = db.get(Document, document_id)
            if document is not None:
                document.status = DocumentStatus.FAILED
                document.error_message = f"{type(e).__name__}: {e}"[:1000]
                db.commit()
            logger.error(f"Embedding failed for document {document_id}: {e}")
    finally:
        db.close()


def reindex_document(db: Session, document: Document) -> int:
    """Re-run normalize -> chunk -> embed from the stored text (e.g. after changing the embedding model)."""
    build_chunks(db, document)
    return embed_document(db, document)
