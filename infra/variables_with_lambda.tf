variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region"
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Environment name"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "CIDR block for VPC"
}

variable "azs" {
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
  description = "Availability zones"
}

variable "public_subnets" {
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
  description = "CIDR blocks for public subnets"
}

variable "private_subnets" {
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
  description = "CIDR blocks for private subnets"
}

variable "s3_bucket_name" {
  type        = string
  description = "S3 bucket for PDF uploads"
}

variable "sqs_queue_name" {
  type        = string
  default     = "indexing-queue"
  description = "SQS queue name for indexing tasks"
}

variable "chromadb_image" {
  type        = string
  default     = "chromadb/chroma:latest"
  description = "ChromaDB container image"
}

variable "backend_image" {
  type        = string
  description = "Backend container image URI"
}

variable "indexer_image" {
  type        = string
  default     = ""
  description = "DEPRECATED: Indexer is now Lambda. Leave empty."
}

variable "bedrock_model_arns" {
  type        = list(string)
  default     = []
  description = "Bedrock model ARNs to grant access"
}

variable "enable_logging" {
  type        = bool
  default     = true
  description = "Enable CloudWatch logging"
}

variable "log_retention_days" {
  type        = number
  default     = 30
  description = "CloudWatch log retention in days"
}

# ===========================
# Lambda-specific variables
# ===========================

variable "lambda_layer_filename" {
  type        = string
  description = "Path to lambda_layer.zip file"
  default     = "./lambda_layer.zip"
}

variable "lambda_function_filename" {
  type        = string
  description = "Path to indexer_lambda.zip file"
  default     = "./indexer_lambda.zip"
}

variable "lambda_memory_size" {
  type        = number
  default     = 1024
  description = "Lambda memory allocation (128-10240 MB)"
}

variable "lambda_timeout" {
  type        = number
  default     = 900
  description = "Lambda timeout in seconds (max 900)"
}

variable "lambda_reserved_concurrency" {
  type        = number
  default     = null
  description = "Reserved concurrent executions for Lambda (null = unreserved)"
}

variable "chunk_size" {
  type        = number
  default     = 1000
  description = "Text chunk size in tokens"
}

variable "chunk_overlap" {
  type        = number
  default     = 200
  description = "Chunk overlap in tokens"
}
