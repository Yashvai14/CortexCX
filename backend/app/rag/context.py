from app.knowledge.model import DocumentChunk


class RAGContextAssembler:
    """Assembles retrieved knowledge into grounded instructions and context for LLM providers."""

    @staticmethod
    def build_grounded_instruction(
        retrieved_chunks: list[tuple[DocumentChunk, float]],
        prompt_override: str | None = None,
    ) -> str:
        instructions = [
            "You are a helpful, accurate, and professional AI Support Assistant for CortexCX.",
            "GROUNDING RULES:",
            "1. Answer the customer inquiry using the provided knowledge context when relevant.",
            "2. Do not invent policies, product information, order information, or facts that are not supported by the available context.",
            "3. If the provided knowledge is insufficient or not relevant to answer the customer's question, politely state that you don't have enough information to resolve the inquiry and that a human support agent will assist them shortly.",
        ]

        if prompt_override:
            instructions.append(f"\nADDITIONAL INSTRUCTIONS:\n{prompt_override}")

        if retrieved_chunks:
            knowledge_blocks = ["\nAVAILABLE KNOWLEDGE CONTEXT:"]
            for idx, (chunk, score) in enumerate(retrieved_chunks, start=1):
                doc_title = (
                    chunk.document.title
                    if chunk.document and chunk.document.title
                    else "Document"
                )
                knowledge_blocks.append(
                    f"--- Source [{idx}]: {doc_title} (Relevance: {score}) ---\n{chunk.content}"
                )
            instructions.append("\n".join(knowledge_blocks))
        else:
            instructions.append(
                "\nAVAILABLE KNOWLEDGE CONTEXT:\nNo relevant knowledge found in the knowledge base."
            )

        return "\n\n".join(instructions)
