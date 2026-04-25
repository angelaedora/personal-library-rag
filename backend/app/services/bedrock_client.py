"""AWS service integrations."""

import json
import base64
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BedrockClient:
    """AWS Bedrock API client for embeddings and LLM."""

    def __init__(self):
        import boto3

        self.settings = get_settings()
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=self.settings.aws_region,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using Bedrock Titan Embeddings."""
        try:
            response = self.client.invoke_model(
                modelId=self.settings.bedrock_embedding_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )

            result = json.loads(response["body"].read().decode("utf-8"))
            return result.get("embedding", [])

        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_response(
        self, prompt: str, max_tokens: int = 2048
    ) -> tuple[str, int]:
        """Generate LLM response using Bedrock Claude."""
        try:
            messages = [{"role": "user", "content": prompt}]

            response = self.client.invoke_model(
                modelId=self.settings.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(
                    {
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                    }
                ),
            )

            result = json.loads(response["body"].read().decode("utf-8"))
            content = result.get("content", [])

            if content and isinstance(content, list):
                text = content[0].get("text", "")
            else:
                text = ""

            usage = result.get("usage", {})
            completion_tokens = usage.get("output_tokens", 0)

            return text, completion_tokens

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise


class S3Client:
    """AWS S3 client for document storage."""

    def __init__(self):
        import boto3

        self.settings = get_settings()
        self.s3 = boto3.client(
            "s3",
            region_name=self.settings.aws_region,
        )

    async def generate_presigned_url(
        self, document_id: str, filename: str, expiration: int = 3600
    ) -> str:
        """Generate presigned URL for PDF upload."""
        key = f"{self.settings.s3_upload_prefix}{document_id}/{filename}"

        url = self.s3.generate_presigned_post(
            Bucket=self.settings.s3_bucket_name,
            Key=key,
            ExpiresIn=expiration,
            Conditions=[
                ["content-length-range", 0, 100 * 1024 * 1024],  # 100MB max
            ],
        )

        return url

    async def get_object(self, document_id: str, filename: str) -> bytes:
        """Retrieve PDF from S3."""
        key = f"{self.settings.s3_upload_prefix}{document_id}/{filename}"

        response = self.s3.get_object(
            Bucket=self.settings.s3_bucket_name,
            Key=key,
        )

        return response["Body"].read()


class SQSClient:
    """AWS SQS client for async indexing tasks."""

    def __init__(self):
        import boto3

        self.settings = get_settings()
        self.sqs = boto3.client(
            "sqs",
            region_name=self.settings.aws_region,
        )

    async def send_indexing_task(
        self, document_id: str, filename: str, s3_key: str
    ) -> str:
        """Queue document for indexing."""
        message_body = json.dumps(
            {
                "document_id": document_id,
                "filename": filename,
                "s3_key": s3_key,
                "action": "index",
            }
        )

        response = self.sqs.send_message(
            QueueUrl=self.settings.sqs_indexing_queue_url,
            MessageBody=message_body,
        )

        return response.get("MessageId", "")
