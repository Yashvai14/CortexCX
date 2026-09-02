from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.providers.factory import get_llm_provider
from app.auth.model import User
from app.conversation.message_model import Message, MessageSenderType
from app.conversation.repositories.conversation_repository import (
    ConversationRepository,
)
from app.conversation.repositories.message_repository import MessageRepository
from app.conversation.schema import MessageResponse
from app.rag.context import RAGContextAssembler
from app.rag.retrieval import RAGRetriever
from app.rag.schema import (
    RAGProcessRequest,
    RAGProcessResponse,
    RAGSourceCitation,
)


class RAGService:

    @staticmethod
    def execute(
        db: Session,
        current_user: User,
        conversation_id: UUID,
        data: RAGProcessRequest | None = None,
    ) -> RAGProcessResponse:
        req = data or RAGProcessRequest()

        conversation_repo = ConversationRepository()
        message_repo = MessageRepository()
        retriever = RAGRetriever()
        assembler = RAGContextAssembler()

        # 1. Tenant boundary check: conversation must belong to user's workspace
        conversation = conversation_repo.get_by_id_and_workspace(
            db=db,
            conversation_id=conversation_id,
            workspace_id=current_user.workspace_id,
        )

        if not conversation:
            raise LookupError("Conversation not found")

        # 2. Verify AI is enabled
        if not conversation.ai_enabled:
            raise ValueError(
                "AI processing is disabled for this conversation"
            )

        # 3. Transition to processing state
        conversation.ai_state = "processing"
        db.commit()
        db.refresh(conversation)

        # 4. Fetch recent conversation messages
        all_messages = message_repo.list_by_conversation(
            db=db,
            conversation_id=conversation.id,
        )
        recent_messages = all_messages[-req.max_history_messages :]

        # Determine the query for knowledge retrieval
        # Prefer the latest customer message; fallback to conversation subject
        customer_messages = [
            m
            for m in recent_messages
            if getattr(m.sender_type, "value", str(m.sender_type)) == "customer"
        ]
        query_text = (
            customer_messages[-1].content
            if customer_messages
            else (
                recent_messages[-1].content
                if recent_messages
                else conversation.subject
            )
        )

        # 5. Retrieve relevant knowledge chunks strictly within workspace
        try:
            retrieved_chunks = retriever.retrieve(
                db=db,
                workspace_id=current_user.workspace_id,
                query=query_text,
                top_k=req.top_k,
            )
        except Exception as e:
            conversation.ai_state = "failed"
            db.commit()
            raise RuntimeError(
                f"Knowledge retrieval failed: {str(e)}"
            ) from None

        # 6. Assemble grounded context instruction
        grounded_instruction = assembler.build_grounded_instruction(
            retrieved_chunks=retrieved_chunks,
            prompt_override=req.prompt_override,
        )

        # 7. Convert message history for LLM provider
        history = [
            {
                "sender_type": (
                    m.sender_type.value
                    if hasattr(m.sender_type, "value")
                    else str(m.sender_type)
                ),
                "content": m.content,
            }
            for m in recent_messages
        ]

        # 8. Invoke LLM provider
        provider = get_llm_provider()

        try:
            response_content = provider.generate_response(
                conversation_subject=conversation.subject,
                messages=history,
                prompt_override=grounded_instruction,
            )
        except Exception as e:
            conversation.ai_state = "failed"
            db.commit()
            raise RuntimeError(
                f"AI provider failed to generate response: {str(e)}"
            ) from None

        # 9. Persist AI-generated response message
        ai_message = Message(
            conversation_id=conversation.id,
            sender_type=MessageSenderType.AI,
            sender_user_id=None,
            content=response_content,
        )
        message_repo.add(db=db, obj=ai_message)

        # 10. Transition conversation to responded state
        conversation.ai_state = "responded"
        db.commit()
        db.refresh(ai_message)
        db.refresh(conversation)

        # 11. Format source citations
        citations: list[RAGSourceCitation] = []
        for chunk, score in retrieved_chunks:
            doc_title = (
                chunk.document.title
                if chunk.document and chunk.document.title
                else None
            )
            ks_id = (
                chunk.document.knowledge_source_id if chunk.document else None
            )
            citations.append(
                RAGSourceCitation(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    knowledge_source_id=ks_id,
                    document_title=doc_title,
                    relevance_score=score,
                    content=chunk.content,
                    metadata_json=chunk.metadata_json,
                )
            )

        provider_name = getattr(
            provider, "model_name", provider.__class__.__name__
        )

        return RAGProcessResponse(
            conversation_id=conversation.id,
            message=MessageResponse.model_validate(ai_message),
            ai_state=conversation.ai_state,
            provider=provider_name,
            sources=citations,
        )
