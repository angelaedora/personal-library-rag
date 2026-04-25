"""Embedding generation for chunks."""

import logging
import json
from typing import List

logger = logging.getLogger(__name__)


class Embedder:
    """Generate embeddings using AWS Bedrock."""

    def __init__(self, bedrock_client):
        """
        Initialize embedder with Bedrock client.

        Args:
            bedrock_client: Bedrock API client instance
        """
        self.bedrock_client = bedrock_client

    async def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple chunks.

        Args:
            chunks: List of text chunks

        Returns:
            List of embedding vectors
        """
        embeddings = []

        for i, chunk in enumerate(chunks):
            try:
                embedding = await self.bedrock_client.generate_embedding(chunk)
                embeddings.append(embedding)

                if (i + 1) % 10 == 0:
                    logger.info(f"Generated embeddings for {i + 1}/{len(chunks)} chunks")

            except Exception as e:
                logger.error(f"Error embedding chunk {i}: {str(e)}")
                raise

        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings

    async def embed_chunk(self, chunk: str) -> List[float]:
        """Generate embedding for single chunk."""
        return await self.bedrock_client.generate_embedding(chunk)
