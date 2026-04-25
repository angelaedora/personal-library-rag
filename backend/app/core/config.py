from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration."""

    # Application
    app_name: str = "Personal Library Assistant"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", validation_alias="ENV")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    log_level: str = Field(default="INFO")

    # AWS
    aws_region: str = Field(default="us-east-1")
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")

    # S3
    s3_bucket_name: str = Field(default="personal-library-pdfs")
    s3_upload_prefix: str = Field(default="uploads/")

    # SQS
    sqs_indexing_queue_url: str = Field(default="")
    sqs_queue_name: str = Field(default="indexing-queue")

    # ChromaDB
    chromadb_host: str = Field(default="localhost")
    chromadb_port: int = Field(default=8000)
    chromadb_http_client_url: str = Field(default="")

    # Bedrock
    bedrock_model_id: str = Field(default="anthropic.claude-3-sonnet-20240229-v1:0")
    bedrock_embedding_model_id: str = Field(default="amazon.titan-embed-text-v2:0")

    # RAG
    rag_top_k: int = Field(default=5)
    rag_chunk_overlap: int = Field(default=200)
    rag_chunk_size: int = Field(default=1000)
    rag_max_context_length: int = Field(default=4000)

    # API
    api_prefix: str = "/api"
    api_timeout_seconds: int = Field(default=30)

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
