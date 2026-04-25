variable "environment" {
  type        = string
  description = "Environment name"
}

variable "queue_name" {
  type        = string
  description = "SQS queue name"
}

resource "aws_sqs_queue" "indexing" {
  name                       = var.queue_name
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 1209600
  visibility_timeout_seconds = 300

  tags = {
    Name = "${var.environment}-indexing-queue"
  }
}

resource "aws_sqs_queue_policy" "indexing" {
  queue_url = aws_sqs_queue.indexing.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.indexing.arn
      }
    ]
  })
}

output "queue_url" {
  value = aws_sqs_queue.indexing.url
}

output "queue_arn" {
  value = aws_sqs_queue.indexing.arn
}

output "queue_name" {
  value = aws_sqs_queue.indexing.name
}
