"""Bedrock client for Lambda."""

import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class BedrockClient:
    """Bedrock API client for embeddings."""

    def __init__(self, client):
        """
        Initialize with boto3 Bedrock client.

        Args:
            client: boto3 bedrock-runtime client
        """
        self.client = client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_embedding(self, text: str) -> list:
        """
        Generate embedding for text using Bedrock Titan Embeddings.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector (list of floats)
        """
        try:
            response = self.client.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )

            result = json.loads(response["body"].read().decode("utf-8"))
            embedding = result.get("embedding", [])

            if not embedding:
                raise ValueError("Empty embedding returned from Bedrock")

            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
