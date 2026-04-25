variable "environment" {
  type        = string
  description = "Environment name"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

resource "aws_security_group" "chromadb" {
  name        = "${var.environment}-chromadb-sg"
  description = "Security group for ChromaDB"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-chromadb-sg"
  }
}

resource "aws_security_group" "backend" {
  name        = "${var.environment}-backend-sg"
  description = "Security group for Backend"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-backend-sg"
  }
}

resource "aws_security_group" "indexer" {
  name        = "${var.environment}-indexer-sg"
  description = "Security group for Indexer"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-indexer-sg"
  }
}

resource "aws_security_group" "efs" {
  name        = "${var.environment}-efs-sg"
  description = "Security group for EFS"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.chromadb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-efs-sg"
  }
}

output "chromadb_sg_id" {
  value = aws_security_group.chromadb.id
}

output "backend_sg_id" {
  value = aws_security_group.backend.id
}

output "indexer_sg_id" {
  value = aws_security_group.indexer.id
}

output "efs_sg_id" {
  value = aws_security_group.efs.id
}
