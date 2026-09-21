from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.ai.tools.base import BaseTool, ToolResult
from app.rag.retrieval import RAGRetriever


class KnowledgeSearchTool(BaseTool):
    name = "knowledge_search"
    description = "Search workspace knowledge documents, guides, and FAQs for authoritative answers to customer questions."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query to match against knowledge chunks"},
            "top_k": {"type": "integer", "description": "Maximum number of relevant chunks to retrieve (default 3)"},
        },
        "required": ["query"],
    }

    def __init__(self):
        self.retriever = RAGRetriever()

    def execute(self, db: Session, workspace_id: UUID, **kwargs: Any) -> ToolResult:
        try:
            query = kwargs.get("query", "").strip()
            if not query:
                return ToolResult(tool_name=self.name, success=False, error="query argument is required")

            top_k = int(kwargs.get("top_k", 3))
            scored_chunks = self.retriever.retrieve(
                db=db,
                workspace_id=workspace_id,
                query=query,
                top_k=top_k,
            )

            results = []
            for chunk, score in scored_chunks:
                doc_title = chunk.document.title if chunk.document else "Knowledge Document"
                results.append({
                    "chunk_id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "document_title": doc_title,
                    "relevance_score": score,
                    "content": chunk.content,
                })

            return ToolResult(
                tool_name=self.name,
                success=True,
                data=results,
            )
        except Exception as e:
            return ToolResult(tool_name=self.name, success=False, error=str(e))
