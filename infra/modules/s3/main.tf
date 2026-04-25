variable "environment" {
  type        = string
  description = "Environment name"
}

variable "bucket_name" {
  type        = string
  description = "S3 bucket name"
}

resource "aws_s3_bucket" "pdf_storage" {
  bucket = var.bucket_name

  tags = {
    Name = "${var.environment}-pdf-storage"
  }
}

resource "aws_s3_bucket_versioning" "pdf_storage" {
  bucket = aws_s3_bucket.pdf_storage.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "pdf_storage" {
  bucket = aws_s3_bucket.pdf_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "pdf_storage" {
  bucket = aws_s3_bucket.pdf_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "pdf_storage" {
  bucket = aws_s3_bucket.pdf_storage.id

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

output "bucket_name" {
  value = aws_s3_bucket.pdf_storage.id
}

output "bucket_arn" {
  value = aws_s3_bucket.pdf_storage.arn
}

output "bucket_region" {
  value = aws_s3_bucket.pdf_storage.region
}
