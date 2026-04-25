"""Vector store client for Lambda."""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)


class VectorStoreClient:
    """ChromaDB vector store client for Lambda."""

    def __init__(self):
        self._client = None
        self._collection = None

    def _get_client(self):
        """Get or create ChromaDB client."""
        if self._client is None:
            import chromadb

            try:
                host = os.getenv("CHROMADB_HOST", "localhost")
                port = int(os.getenv("CHROMADB_PORT", "8000"))
                url = f"http://{host}:{port}"

                self._client = chromadb.HttpClient(url=url)
                logger.info(f"Connected to ChromaDB at {url}")

            except Exception as e:
                logger.error(f"Failed to connect to ChromaDB: {str(e)}")
                raise

        return self._client

    def _get_collection(self):
        """Get or create collection."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )

        return self._collection

    async def add_chunks(
        self,
        document_id: str,
        chunk_ids: List[str],
        embeddings: List[List[float]],
        chunks: List[str],
        metadata: List[dict],
    ) -> bool:
        """Add chunks to vector store."""
        try:
            collection = self._get_collection()

            collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadata,
            )

            logger.info(
                f"Added {len(chunk_ids)} chunks for document {document_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error adding chunks: {str(e)}")
            raise

    async def delete_document_chunks(self, document_id: str) -> int:
        """Delete all chunks for document."""
        try:
            collection = self._get_collection()

            results = collection.get(
                where={"document_id": {"$eq": document_id}}
            )

            if results["ids"]:
                collection.delete(ids=results["ids"])
                deleted_count = len(results["ids"])
                logger.info(
                    f"Deleted {deleted_count} chunks for document {document_id}"
                )
                return deleted_count

            return 0

        except Exception as e:
            logger.error(f"Error deleting chunks: {str(e)}")
            raise
