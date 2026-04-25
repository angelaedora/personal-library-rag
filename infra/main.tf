terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "personal-library-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "personal-library-assistant"
      ManagedBy   = "Terraform"
    }
  }
}

module "vpc" {
  source = "./modules/vpc"

  environment    = var.environment
  vpc_cidr       = var.vpc_cidr
  azs            = var.azs
  public_subnets = var.public_subnets
  private_subnets = var.private_subnets
}

module "security" {
  source = "./modules/security"

  environment = var.environment
  vpc_id      = module.vpc.vpc_id
}

module "efs" {
  source = "./modules/efs"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  security_group_ids = [module.security.efs_sg_id]
}

module "s3" {
  source = "./modules/s3"

  environment = var.environment
  bucket_name = var.s3_bucket_name
}

module "sqs" {
  source = "./modules/sqs"

  environment = var.environment
  queue_name  = var.sqs_queue_name
}

module "iam" {
  source = "./modules/iam"

  environment          = var.environment
  s3_bucket_arn        = module.s3.bucket_arn
  sqs_queue_arn        = module.sqs.queue_arn
  bedrock_model_arns   = var.bedrock_model_arns
}

module "ecs" {
  source = "./modules/ecs"

  environment = var.environment
}

module "chromadb" {
  source = "./modules/ecs"

  environment           = var.environment
  ecs_cluster_name      = module.ecs.cluster_name
  service_name          = "chromadb"
  container_image       = var.chromadb_image
  container_port        = 8000
  cpu                   = 512
  memory                = 1024
  desired_count         = 1
  subnets               = module.vpc.private_subnet_ids
  security_groups       = [module.security.chromadb_sg_id]
  efs_volume_name       = "chromadb-data"
  efs_file_system_id    = module.efs.file_system_id
  efs_access_point_id   = module.efs.chromadb_access_point_id
  task_role_arn         = module.iam.ecs_task_role_arn
  execution_role_arn    = module.iam.ecs_execution_role_arn

  depends_on = [module.efs]
}

module "backend" {
  source = "./modules/ecs"

  environment           = var.environment
  ecs_cluster_name      = module.ecs.cluster_name
  service_name          = "backend"
  container_image       = var.backend_image
  container_port        = 8000
  cpu                   = 256
  memory                = 512
  desired_count         = 2
  subnets               = module.vpc.private_subnet_ids
  security_groups       = [module.security.backend_sg_id]
  task_role_arn         = module.iam.ecs_task_role_arn
  execution_role_arn    = module.iam.ecs_execution_role_arn

  environment_variables = {
    CHROMADB_HOST           = module.chromadb.service_endpoint
    CHROMADB_PORT           = "8000"
    S3_BUCKET_NAME          = module.s3.bucket_name
    SQS_INDEXING_QUEUE_URL  = module.sqs.queue_url
    BEDROCK_REGION          = var.aws_region
    LOG_LEVEL               = "INFO"
  }

  depends_on = [module.chromadb]
}

module "indexer" {
  source = "./modules/ecs"

  environment           = var.environment
  ecs_cluster_name      = module.ecs.cluster_name
  service_name          = "indexer"
  container_image       = var.indexer_image
  cpu                   = 512
  memory                = 1024
  desired_count         = 1
  subnets               = module.vpc.private_subnet_ids
  security_groups       = [module.security.indexer_sg_id]
  task_role_arn         = module.iam.ecs_task_role_arn
  execution_role_arn    = module.iam.ecs_execution_role_arn

  environment_variables = {
    CHROMADB_HOST         = module.chromadb.service_endpoint
    CHROMADB_PORT         = "8000"
    S3_BUCKET             = module.s3.bucket_name
    SQS_QUEUE_URL         = module.sqs.queue_url
    AWS_REGION            = var.aws_region
    CHUNK_SIZE            = "1000"
    CHUNK_OVERLAP         = "200"
    LOG_LEVEL             = "INFO"
  }

  depends_on = [module.chromadb]
}

output "backend_endpoint" {
  description = "Backend API endpoint"
  value       = module.backend.service_endpoint
}

output "chromadb_endpoint" {
  description = "ChromaDB endpoint (internal only)"
  value       = module.chromadb.service_endpoint
}

output "sqs_queue_url" {
  description = "SQS indexing queue URL"
  value       = module.sqs.queue_url
}

output "s3_bucket_name" {
  description = "S3 bucket for PDFs"
  value       = module.s3.bucket_name
}
