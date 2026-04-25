"""Vector store integration with ChromaDB."""

import logging
from typing import Optional, List
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.core.models import ChunkWithScore

logger = logging.getLogger(__name__)


class VectorStoreClient:
    """ChromaDB vector store client."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[chromadb.HttpClient] = None
        self._collection = None

    def _get_client(self) -> chromadb.HttpClient:
        """Get or create ChromaDB HTTP client."""
        if self._client is None:
            try:
                # Build ChromaDB URL from config
                if self.settings.chromadb_http_client_url:
                    url = self.settings.chromadb_http_client_url
                else:
                    url = f"http://{self.settings.chromadb_host}:{self.settings.chromadb_port}"

                self._client = chromadb.HttpClient(url=url)
                logger.info(f"Connected to ChromaDB at {url}")

            except Exception as e:
                logger.error(f"Failed to connect to ChromaDB: {str(e)}")
                raise

        return self._client

    def _get_collection(self) -> chromadb.Collection:
        """Get or create document collection."""
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
        """Add document chunks to vector store."""
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
            logger.error(
                f"Error adding chunks for {document_id}: {str(e)}"
            )
            raise

    async def query(
        self,
        embedding: List[float],
        top_k: int,
        document_filters: Optional[List[str]] = None,
    ) -> List[ChunkWithScore]:
        """Query vector store for similar chunks."""
        try:
            collection = self._get_collection()

            # Build filter if document IDs specified
            where_filter = None
            if document_filters:
                where_filter = {
                    "document_id": {"$in": document_filters}
                }

            results = collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            # Convert distances to similarity scores (ChromaDB uses cosine distance)
            chunks = []
            if results["ids"] and results["ids"][0]:
                for i, chunk_id in enumerate(results["ids"][0]):
                    # Convert cosine distance to similarity (1 - distance)
                    distance = results["distances"][0][i]
                    similarity = 1 - distance  # For cosine distance

                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}

                    chunk = ChunkWithScore(
                        chunk_id=chunk_id,
                        content=results["documents"][0][i],
                        score=max(0.0, similarity),  # Ensure non-negative
                        document_id=metadata.get("document_id", ""),
                        page_number=metadata.get("page_number"),
                        chunk_index=metadata.get("chunk_index"),
                    )
                    chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"Error querying vector store: {str(e)}")
            raise

    async def delete_document_chunks(self, document_id: str) -> int:
        """Delete all chunks for a document (idempotent re-indexing)."""
        try:
            collection = self._get_collection()

            # Get all chunk IDs for this document
            results = collection.get(
                where={"document_id": {"$eq": document_id}}
            )

            if results["ids"]:
                collection.delete(ids=results["ids"])
                deleted_count = len(results["ids"])
                logger.info(f"Deleted {deleted_count} chunks for document {document_id}")
                return deleted_count

            return 0

        except Exception as e:
            logger.error(f"Error deleting chunks for {document_id}: {str(e)}")
            raise

    async def get_document_chunks(
        self, document_id: str
    ) -> List[dict]:
        """Get all chunks for a document."""
        try:
            collection = self._get_collection()

            results = collection.get(
                where={"document_id": {"$eq": document_id}},
                include=["documents", "metadatas"],
            )

            chunks = []
            for i, chunk_id in enumerate(results["ids"]):
                chunks.append({
                    "id": chunk_id,
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i],
                })

            return chunks

        except Exception as e:
            logger.error(f"Error retrieving chunks for {document_id}: {str(e)}")
            raise
