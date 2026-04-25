"""RAG pipeline orchestration."""

import logging
import time
from typing import List

from app.core.config import get_settings
from app.core.models import RAGContext, SourceAttribution, ChatResponse, ChatMessage
from app.services.bedrock_client import BedrockClient
from app.services.vector_store import VectorStoreClient

logger = logging.getLogger(__name__)


class RAGService:
    """Orchestrates retrieval-augmented generation."""

    def __init__(self):
        self.settings = get_settings()
        self.bedrock = BedrockClient()
        self.vector_store = VectorStoreClient()

    async def retrieve_context(
        self,
        query: str,
        top_k: int = None,
        document_filters: List[str] = None,
    ) -> RAGContext:
        """Retrieve relevant chunks from vector store."""
        if top_k is None:
            top_k = self.settings.rag_top_k

        start_time = time.time()

        try:
            # Step 1: Generate query embedding
            query_embedding = await self.bedrock.generate_embedding(query)

            # Step 2: Retrieve similar chunks
            chunks = await self.vector_store.query(
                embedding=query_embedding,
                top_k=top_k,
                document_filters=document_filters,
            )

            retrieval_time_ms = (time.time() - start_time) * 1000

            # Get unique documents in results
            unique_docs = set(chunk.document_id for chunk in chunks)

            context = RAGContext(
                chunks=chunks,
                total_documents=len(unique_docs),
                retrieval_time_ms=retrieval_time_ms,
            )

            logger.info(
                f"Retrieved {len(chunks)} chunks in {retrieval_time_ms:.2f}ms"
            )

            return context

        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            raise

    def _build_rag_prompt(
        self, query: str, context_chunks: List, chat_history: List[ChatMessage]
    ) -> str:
        """Build complete prompt with context and history."""
        # Build context section
        context_section = "# REFERENCE DOCUMENTS\n\n"
        for i, chunk in enumerate(context_chunks, 1):
            context_section += f"## Source {i}: {chunk.document_id}\n"
            context_section += f"```\n{chunk.content}\n```\n\n"

        # Build chat history section
        history_section = ""
        if chat_history:
            history_section = "# CONVERSATION HISTORY\n\n"
            for msg in chat_history:
                history_section += f"{msg.role.upper()}: {msg.content}\n\n"

        # Build final prompt
        prompt = f"""You are a helpful assistant that answers questions based strictly on provided reference documents.

{context_section}

{history_section}

# INSTRUCTIONS
1. Answer the user's question using ONLY information from the reference documents above
2. If the answer is not in the documents, say "I cannot find this information in the provided documents"
3. Always cite which source you're referencing
4. Be concise and accurate

# QUESTION
{query}

Please provide your answer:"""

        return prompt

    async def generate_response(
        self,
        query: str,
        context: RAGContext,
        chat_history: List[ChatMessage] = None,
    ) -> ChatResponse:
        """Generate answer using retrieved context."""
        if chat_history is None:
            chat_history = []

        start_time = time.time()

        try:
            # Step 1: Build RAG prompt
            prompt = self._build_rag_prompt(query, context.chunks, chat_history)

            # Step 2: Generate response
            response_text, tokens_used = await self.bedrock.generate_response(
                prompt=prompt,
                max_tokens=2048,
            )

            generation_time_ms = (time.time() - start_time) * 1000

            # Step 3: Format source attributions
            sources: List[SourceAttribution] = []
            for chunk in context.chunks:
                # Avoid duplicate sources
                if not any(s.document_id == chunk.document_id for s in sources):
                    sources.append(
                        SourceAttribution(
                            document_id=chunk.document_id,
                            filename=chunk.document_id,  # In production, look this up from metadata
                            page_number=chunk.page_number,
                            relevance_score=chunk.score,
                        )
                    )

            chat_response = ChatResponse(
                answer=response_text,
                sources=sources,
                retrieval_time_ms=context.retrieval_time_ms,
                generation_time_ms=generation_time_ms,
                model_used=self.settings.bedrock_model_id,
            )

            logger.info(
                f"Generated response in {generation_time_ms:.2f}ms "
                f"using {len(context.chunks)} chunks"
            )

            return chat_response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    async def process_query(
        self,
        query: str,
        chat_history: List[ChatMessage] = None,
        top_k: int = None,
        document_filters: List[str] = None,
    ) -> ChatResponse:
        """End-to-end query processing: retrieve → generate."""
        try:
            # Retrieve context
            context = await self.retrieve_context(
                query=query,
                top_k=top_k,
                document_filters=document_filters,
            )

            # Generate response
            response = await self.generate_response(
                query=query,
                context=context,
                chat_history=chat_history or [],
            )

            return response

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            raise
