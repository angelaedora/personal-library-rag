"""Write chunks to vector store for Lambda."""

import logging
from typing import List

logger = logging.getLogger(__name__)


class VectorWriter:
    """Write chunked documents to vector store."""

    def __init__(self, vector_store_client):
        """
        Initialize writer with vector store client.

        Args:
            vector_store_client: ChromaDB client instance
        """
        self.vector_store_client = vector_store_client

    async def write_chunks(
        self,
        document_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata_list: List[dict],
        filename: str = "",
    ) -> bool:
        """
        Write chunks to vector store.

        Args:
            document_id: Unique document identifier
            chunks: List of text chunks
            embeddings: List of embedding vectors
            metadata_list: List of metadata dicts for each chunk
            filename: Original filename for metadata

        Returns:
            Success status
        """
        try:
            # Generate chunk IDs
            chunk_ids = [f"{document_id}-chunk-{i}" for i in range(len(chunks))]

            # Enrich metadata with document info
            enriched_metadata = []
            for meta in metadata_list:
                meta["document_id"] = document_id
                meta["filename"] = filename
                enriched_metadata.append(meta)

            # Write to vector store
            await self.vector_store_client.add_chunks(
                document_id=document_id,
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                chunks=chunks,
                metadata=enriched_metadata,
            )

            logger.info(
                f"Wrote {len(chunks)} chunks for document {document_id} to vector store"
            )

            return True

        except Exception as e:
            logger.error(f"Error writing chunks: {str(e)}")
            raise
