variable "environment" {
  type        = string
  description = "Environment name"
}

variable "s3_bucket_arn" {
  type        = string
  description = "S3 bucket ARN for PDFs"
}

variable "sqs_queue_arn" {
  type        = string
  description = "SQS queue ARN for indexing tasks"
}

variable "chromadb_host" {
  type        = string
  description = "ChromaDB hostname"
}

variable "chromadb_port" {
  type        = number
  default     = 8000
  description = "ChromaDB port"
}

variable "bedrock_model_arns" {
  type        = list(string)
  default     = []
  description = "Bedrock model ARNs to grant access"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for Lambda (VPC)"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs for Lambda"
}

variable "lambda_layer_filename" {
  type        = string
  description = "Path to lambda_layer.zip"
}

variable "lambda_function_filename" {
  type        = string
  description = "Path to indexer_lambda.zip"
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

variable "log_retention_days" {
  type        = number
  default     = 30
  description = "CloudWatch log retention"
}

variable "memory_size" {
  type        = number
  default     = 1024
  description = "Lambda memory allocation (128-10240 MB)"
  validation {
    condition     = var.memory_size >= 128 && var.memory_size <= 10240
    error_message = "Memory must be between 128 and 10240 MB."
  }
}

variable "timeout" {
  type        = number
  default     = 900
  description = "Lambda timeout in seconds (max 900)"
}

variable "reserved_concurrent_executions" {
  type        = number
  default     = 100
  description = "Reserved concurrent executions (null = unreserved)"
}

# ===========================
# IAM Role for Lambda
# ===========================

resource "aws_iam_role" "lambda_indexer_role" {
  name = "${var.environment}-lambda-indexer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-lambda-indexer-role"
    Environment = var.environment
  }
}

# ===========================
# IAM Policies
# ===========================

# VPC Execution Policy
resource "aws_iam_role_policy" "lambda_vpc_execution" {
  name = "${var.environment}-lambda-vpc-execution"
  role = aws_iam_role.lambda_indexer_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}

# S3 Access Policy
resource "aws_iam_role_policy" "lambda_s3_access" {
  name = "${var.environment}-lambda-s3-access"
  role = aws_iam_role.lambda_indexer_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${var.s3_bucket_arn}/*"
      }
    ]
  })
}

# Bedrock Access Policy
resource "aws_iam_role_policy" "lambda_bedrock_access" {
  count = length(var.bedrock_model_arns) > 0 ? 1 : 0
  name  = "${var.environment}-lambda-bedrock-access"
  role  = aws_iam_role.lambda_indexer_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = var.bedrock_model_arns
      }
    ]
  })
}

# CloudWatch Logs Policy
resource "aws_iam_role_policy" "lambda_logs" {
  name = "${var.environment}-lambda-logs"
  role = aws_iam_role.lambda_indexer_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ===========================
# CloudWatch Log Group
# ===========================

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.environment}-indexer"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.environment}-lambda-logs"
    Environment = var.environment
  }
}

# ===========================
# Lambda Layer (Dependencies)
# ===========================

resource "aws_lambda_layer_version" "dependencies" {
  filename            = var.lambda_layer_filename
  layer_name          = "${var.environment}-indexer-dependencies"
  compatible_runtimes = ["python3.11"]
  source_code_hash    = filebase64sha256(var.lambda_layer_filename)

  depends_on = [aws_iam_role.lambda_indexer_role]
}

# ===========================
# Lambda Function
# ===========================

resource "aws_lambda_function" "indexer" {
  filename         = var.lambda_function_filename
  function_name    = "${var.environment}-indexer"
  role             = aws_iam_role.lambda_indexer_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.11"
  timeout          = var.timeout
  memory_size      = var.memory_size
  source_code_hash = filebase64sha256(var.lambda_function_filename)

  layers = [
    aws_lambda_layer_version.dependencies.arn
  ]

  environment {
    variables = {
      S3_BUCKET         = split("/", var.s3_bucket_arn)[5]
      CHROMADB_HOST     = var.chromadb_host
      CHROMADB_PORT     = tostring(var.chromadb_port)
      CHUNK_SIZE        = tostring(var.chunk_size)
      CHUNK_OVERLAP     = tostring(var.chunk_overlap)
      LOG_LEVEL         = "INFO"
      AWS_REGION        = data.aws_caller_identity.current.region
    }
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }

  depends_on = [
    aws_iam_role_policy.lambda_vpc_execution,
    aws_iam_role_policy.lambda_s3_access,
    aws_cloudwatch_log_group.lambda_logs
  ]

  tags = {
    Name        = "${var.environment}-indexer"
    Environment = var.environment
    Service     = "indexer"
  }
}

# ===========================
# Lambda Reserved Concurrency
# ===========================

resource "aws_lambda_provisioned_concurrency_config" "indexer" {
  count                             = var.reserved_concurrent_executions != null ? 1 : 0
  function_name                     = aws_lambda_function.indexer.function_name
  provisioned_concurrent_executions = var.reserved_concurrent_executions
  qualifier                         = aws_lambda_function.indexer.version
}

# ===========================
# SQS Event Source Mapping
# ===========================

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.indexer.arn
  batch_size       = 1
  enabled          = true

  # Longer timeout for batch processing (SQS message visibility)
  maximum_batching_window_in_seconds = 5

  # Error handling
  function_response_types = ["ReportBatchItemFailures"]

  depends_on = [aws_lambda_function.indexer]
}

# ===========================
# CloudWatch Alarms
# ===========================

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.environment}-indexer-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when Lambda indexer has errors"

  dimensions = {
    FunctionName = aws_lambda_function.indexer.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.environment}-indexer-lambda-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  threshold           = 300000  # 5 minutes in milliseconds
  alarm_description   = "Alert when Lambda execution time exceeds 5 minutes"

  dimensions = {
    FunctionName = aws_lambda_function.indexer.function_name
  }
}

# ===========================
# Data Sources
# ===========================

data "aws_caller_identity" "current" {}

# ===========================
# Outputs
# ===========================

output "lambda_function_arn" {
  description = "ARN of Lambda indexer function"
  value       = aws_lambda_function.indexer.arn
}

output "lambda_function_name" {
  description = "Name of Lambda indexer function"
  value       = aws_lambda_function.indexer.function_name
}

output "lambda_role_arn" {
  description = "ARN of Lambda execution role"
  value       = aws_iam_role.lambda_indexer_role.arn
}

output "lambda_log_group" {
  description = "CloudWatch log group for Lambda"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "event_source_mapping_uuid" {
  description = "UUID of SQS event source mapping"
  value       = aws_lambda_event_source_mapping.sqs_trigger.uuid
}
