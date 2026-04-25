"""Main indexer worker loop."""

import asyncio
import json
import logging
import sys
from typing import Optional

import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from app.pdf_parser import PDFExtractor
from app.chunker import TextChunker
from app.embedder import Embedder
from app.vector_writer import VectorWriter

logger = logging.getLogger(__name__)


class IndexerConfig:
    """Configuration for indexer."""

    def __init__(self):
        import os

        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.s3_bucket = os.getenv("S3_BUCKET", "personal-library-pdfs")
        self.sqs_queue_url = os.getenv("SQS_QUEUE_URL", "")
        self.chromadb_host = os.getenv("CHROMADB_HOST", "localhost")
        self.chromadb_port = os.getenv("CHROMADB_PORT", "8000")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.visibility_timeout = int(os.getenv("VISIBILITY_TIMEOUT", "300"))


class IndexerWorker:
    """Worker that processes indexing tasks from SQS."""

    def __init__(self, config: IndexerConfig):
        self.config = config
        self.s3_client = boto3.client("s3", region_name=config.aws_region)
        self.sqs_client = boto3.client("sqs", region_name=config.aws_region)
        self.bedrock_client = boto3.client(
            "bedrock-runtime", region_name=config.aws_region
        )

        # Import here to use configured clients
        from app.bedrock_client import BedrockClient as ClientWrapper
        from app.vector_store import VectorStoreClient

        # Monkey-patch to use our configured client
        self.bedrock_wrapper = ClientWrapper()
        self.bedrock_wrapper.client = self.bedrock_client

        self.vector_store = VectorStoreClient()
        self.vector_store._client = None  # Reset to use configured host

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _download_pdf(self, s3_key: str) -> bytes:
        """Download PDF from S3."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.config.s3_bucket,
                Key=s3_key,
            )
            pdf_bytes = response["Body"].read()
            logger.info(f"Downloaded {len(pdf_bytes)} bytes from S3: {s3_key}")
            return pdf_bytes

        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")
            raise

    async def _index_document(
        self,
        document_id: str,
        filename: str,
        s3_key: str,
    ) -> bool:
        """Process single document indexing task."""
        try:
            logger.info(f"Starting indexing for document: {document_id}")

            # Step 1: Download PDF
            pdf_bytes = await self._download_pdf(s3_key)

            # Step 2: Extract text
            extractor = PDFExtractor()
            text, page_count = extractor.extract_text_with_pages(pdf_bytes)
            logger.info(f"Extracted {page_count} pages from PDF")

            # Step 3: Delete existing chunks (idempotent)
            existing_chunks = await self.vector_store.delete_document_chunks(
                document_id
            )
            logger.info(f"Deleted {existing_chunks} existing chunks for document")

            # Step 4: Chunk text
            chunker = TextChunker(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )
            chunks = chunker.chunk(text)
            logger.info(f"Created {len(chunks)} chunks")

            # Step 5: Generate embeddings
            embedder = Embedder(self.bedrock_wrapper)
            embeddings = await embedder.embed_chunks(chunks)

            # Step 6: Create metadata
            metadata_list = [
                {
                    "page_number": 1,
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                }
                for i in range(len(chunks))
            ]

            # Step 7: Write to vector store
            writer = VectorWriter(self.vector_store)
            await writer.write_chunks(
                document_id=document_id,
                chunks=chunks,
                embeddings=embeddings,
                metadata_list=metadata_list,
                filename=filename,
            )

            logger.info(f"Successfully indexed document: {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error indexing document {document_id}: {str(e)}")
            raise

    async def _process_message(self, message: dict) -> bool:
        """Process single SQS message."""
        try:
            body = json.loads(message["Body"])

            document_id = body.get("document_id")
            filename = body.get("filename")
            s3_key = body.get("s3_key")

            if not all([document_id, filename, s3_key]):
                logger.error(f"Invalid message body: {body}")
                return False

            # Index the document
            await self._index_document(document_id, filename, s3_key)

            # Delete from queue
            self.sqs_client.delete_message(
                QueueUrl=self.config.sqs_queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )

            logger.info(f"Processed and deleted message for document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            # Return False to leave message in queue for retry
            return False

    async def _fetch_messages(self) -> list:
        """Fetch messages from SQS."""
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.config.sqs_queue_url,
                MaxNumberOfMessages=10,
                VisibilityTimeout=self.config.visibility_timeout,
                WaitTimeSeconds=5,
            )

            return response.get("Messages", [])

        except Exception as e:
            logger.error(f"Error fetching messages: {str(e)}")
            return []

    async def run(self) -> None:
        """Main worker loop."""
        logger.info("Starting indexer worker")

        while True:
            try:
                messages = await self._fetch_messages()

                if not messages:
                    logger.debug("No messages in queue, waiting...")
                    await asyncio.sleep(5)
                    continue

                logger.info(f"Processing {len(messages)} messages")

                for message in messages:
                    try:
                        await self._process_message(message)
                    except Exception as e:
                        logger.error(f"Error in message processing: {str(e)}")

                await asyncio.sleep(1)

            except KeyboardInterrupt:
                logger.info("Shutting down worker")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                await asyncio.sleep(10)


async def main():
    """Main entrypoint."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = IndexerConfig()

    if not config.sqs_queue_url:
        logger.error("SQS_QUEUE_URL environment variable is required")
        sys.exit(1)

    worker = IndexerWorker(config)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
