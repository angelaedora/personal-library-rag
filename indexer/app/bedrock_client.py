"""AWS Bedrock client for indexer."""

import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class BedrockClient:
    """Bedrock API client for embeddings."""

    def __init__(self, client=None):
        self.client = client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text."""
        try:
            response = self.client.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )

            result = json.loads(response["body"].read().decode("utf-8"))
            return result.get("embedding", [])

        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
