"""Chat API routes."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from app.core.models import ChatRequest, ChatResponse
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_rag_service() -> RAGService:
    """Dependency injection for RAG service."""
    return RAGService()


@router.post("/query", response_model=ChatResponse)
async def query_documents(
    request: ChatRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> ChatResponse:
    """
    Query documents using RAG.

    - **query**: The user's question
    - **messages**: Conversation history (optional)
    - **top_k**: Number of document chunks to retrieve (1-20, default 5)
    """
    try:
        response = await rag_service.process_query(
            query=request.query,
            chat_history=request.messages,
            top_k=request.top_k,
        )

        return response

    except ValueError as e:
        logger.error(f"Validation error in query: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
