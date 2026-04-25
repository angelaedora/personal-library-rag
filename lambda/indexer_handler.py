"""
Lambda handler for document indexing.
Processes SQS events and indexes PDFs into ChromaDB.
"""

import json
import logging
import os
from typing import Any, Dict, List

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Initialize AWS clients (reused across warm starts)
s3_client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
bedrock_client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Import indexer modules
from indexer_modules.pdf_parser import PDFExtractor
from indexer_modules.chunker import TextChunker
from indexer_modules.embedder import Embedder
from indexer_modules.vector_writer import VectorWriter
from indexer_modules.bedrock_client import BedrockClient
from indexer_modules.vector_store import VectorStoreClient


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for document indexing.
    Triggered by SQS events from S3 uploads.

    Args:
        event: SQS event with Records containing document tasks
        context: Lambda context object

    Returns:
        Dict with processing results (statusCode, body)
    """
    try:
        logger.info(f"Processing SQS batch: {len(event.get('Records', []))} messages")

        # Process each SQS message
        failed_messages = []
        successful_count = 0

        for record in event.get("Records", []):
            try:
                message_id = record.get("messageId", "unknown")

                # Parse SQS message body
                body = json.loads(record["body"])

                document_id = body.get("document_id")
                filename = body.get("filename")
                s3_key = body.get("s3_key")

                # Validate required fields
                if not all([document_id, filename, s3_key]):
                    logger.error(f"Invalid message {message_id}: missing required fields")
                    failed_messages.append({
                        "messageId": message_id,
                        "reason": "missing_required_fields"
                    })
                    continue

                logger.info(f"Processing document: {document_id}")

                # Index the document
                _index_document(document_id, filename, s3_key)
                successful_count += 1
                logger.info(f"Successfully indexed {document_id}")

            except ValueError as e:
                logger.error(f"Validation error in message {message_id}: {str(e)}")
                failed_messages.append({
                    "messageId": message_id,
                    "reason": "validation_error",
                    "error": str(e)
                })
            except Exception as e:
                logger.error(f"Failed to process message {message_id}: {str(e)}", exc_info=True)
                failed_messages.append({
                    "messageId": message_id,
                    "reason": "processing_error",
                    "error": str(e)
                })

        # Return results
        response = {
            "statusCode": 200 if failed_messages == [] else 206,  # 206 = Partial Content
            "body": json.dumps({
                "processed": successful_count,
                "failed": len(failed_messages),
                "failed_messages": failed_messages,
                "execution_duration": int(context.get_remaining_time_in_millis() / 1000) if hasattr(context, 'get_remaining_time_in_millis') else None
            })
        }

        logger.info(f"Batch processing complete: {successful_count} success, {len(failed_messages)} failed")
        return response

    except Exception as e:
        logger.error(f"Critical error in Lambda handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Lambda handler failed",
                "message": str(e)
            })
        }


def _index_document(document_id: str, filename: str, s3_key: str) -> None:
    """
    Index a single document from S3 into ChromaDB.

    Args:
        document_id: Unique document identifier
        filename: Original PDF filename
        s3_key: S3 object key

    Raises:
        Exception: If any step fails
    """
    try:
        # Step 1: Download PDF from S3
        logger.info(f"Downloading {s3_key} from S3")
        s3_response = s3_client.get_object(
            Bucket=os.getenv("S3_BUCKET"),
            Key=s3_key
        )
        pdf_bytes = s3_response["Body"].read()
        logger.info(f"Downloaded {len(pdf_bytes)} bytes")

        # Step 2: Extract text from PDF
        logger.info(f"Extracting text from {filename}")
        extractor = PDFExtractor()
        text, page_count = extractor.extract_text_with_pages(pdf_bytes)
        logger.info(f"Extracted {page_count} pages, {len(text)} characters")

        # Step 3: Initialize services
        bedrock_wrapper = BedrockClient(bedrock_client)
        vector_store = VectorStoreClient()

        # Step 4: Delete existing chunks (idempotent re-indexing)
        logger.info(f"Deleting existing chunks for {document_id}")
        deleted_count = vector_store.delete_document_chunks(document_id)
        logger.info(f"Deleted {deleted_count} existing chunks")

        # Step 5: Chunk text with overlap
        logger.info("Chunking text")
        chunker = TextChunker(
            chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200"))
        )
        chunks = chunker.chunk(text)
        logger.info(f"Created {len(chunks)} chunks")

        if not chunks:
            raise ValueError("No chunks generated from text")

        # Step 6: Generate embeddings for all chunks
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        embedder = Embedder(bedrock_wrapper)
        embeddings = embedder.embed_chunks(chunks)
        logger.info(f"Generated {len(embeddings)} embeddings")

        # Step 7: Create metadata for each chunk
        metadata_list = [
            {
                "page_number": 1,
                "chunk_index": i,
                "chunk_count": len(chunks),
            }
            for i in range(len(chunks))
        ]

        # Step 8: Write chunks to ChromaDB
        logger.info("Writing chunks to ChromaDB")
        writer = VectorWriter(vector_store)
        writer.write_chunks(
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings,
            metadata_list=metadata_list,
            filename=filename
        )

        logger.info(f"Successfully indexed {document_id} with {len(chunks)} chunks")

    except Exception as e:
        logger.error(f"Error indexing document {document_id}: {str(e)}", exc_info=True)
        raise
