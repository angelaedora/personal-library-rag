"""Document management routes."""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from app.core.models import UploadResponse
from app.core.config import get_settings
from app.services.bedrock_client import S3Client, SQSClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])


def get_s3_client() -> S3Client:
    """Dependency injection for S3 client."""
    return S3Client()


def get_sqs_client() -> SQSClient:
    """Dependency injection for SQS client."""
    return SQSClient()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    s3_client: S3Client = Depends(get_s3_client),
    sqs_client: SQSClient = Depends(get_sqs_client),
) -> UploadResponse:
    """
    Upload a PDF document for indexing.

    - **file**: PDF file to upload (max 100MB)
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported",
            )

        # Generate document ID
        document_id = str(uuid.uuid4())

        # Read file content
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="File too large (max 100MB)",
            )

        # Generate S3 key
        s3_key = f"uploads/{document_id}/{file.filename}"

        # Queue for indexing
        message_id = await sqs_client.send_indexing_task(
            document_id=document_id,
            filename=file.filename,
            s3_key=s3_key,
        )

        logger.info(
            f"Queued document {document_id} for indexing, message: {message_id}"
        )

        return UploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="indexing_queued",
            s3_key=s3_key,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("/list")
async def list_documents() -> dict:
    """
    List indexed documents.

    Note: Full implementation would retrieve from metadata store/database.
    """
    return {
        "documents": [],
        "total": 0,
    }


@router.delete("/{document_id}")
async def delete_document(document_id: str) -> dict:
    """
    Delete a document and its chunks.

    - **document_id**: UUID of document to delete
    """
    try:
        from app.services.vector_store import VectorStoreClient
        
        vector_store = VectorStoreClient()
        deleted_chunks = await vector_store.delete_document_chunks(document_id)

        logger.info(f"Deleted document {document_id}")

        return {
            "document_id": document_id,
            "chunks_deleted": deleted_chunks,
        }

    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail="Deletion failed")
