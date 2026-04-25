"""Core application models and schemas."""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DocumentMetadata(BaseModel):
    """Metadata for indexed documents."""

    document_id: str
    filename: str
    upload_timestamp: datetime
    page_count: int
    total_chunks: int


class ChunkWithScore(BaseModel):
    """Retrieved chunk with similarity score."""

    chunk_id: str
    content: str
    score: float = Field(..., ge=0.0, le=1.0)
    document_id: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None


class RAGContext(BaseModel):
    """Context assembled for RAG."""

    chunks: List[ChunkWithScore]
    total_documents: int
    retrieval_time_ms: float


class ChatMessage(BaseModel):
    """Single message in chat."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    """Chat endpoint request."""

    messages: List[ChatMessage]
    query: str
    top_k: Optional[int] = Field(default=5, ge=1, le=20)


class SourceAttribution(BaseModel):
    """Attribution for a source chunk."""

    document_id: str
    filename: str
    page_number: Optional[int] = None
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    """Chat endpoint response."""

    answer: str
    sources: List[SourceAttribution]
    retrieval_time_ms: float
    generation_time_ms: float
    model_used: str


class UploadRequest(BaseModel):
    """File upload request metadata."""

    filename: str
    content_type: str


class UploadResponse(BaseModel):
    """File upload response."""

    document_id: str
    filename: str
    status: str = Field(default="indexing_queued")
    s3_key: str


class IndexingTask(BaseModel):
    """Indexing task metadata."""

    task_id: str
    document_id: str
    filename: str
    status: str = Field(default="pending")
    created_at: datetime
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None
