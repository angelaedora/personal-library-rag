variable "environment" {
  type        = string
  description = "Environment name"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for EFS"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs"
}

resource "aws_efs_file_system" "chromadb" {
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = {
    Name = "${var.environment}-chromadb-efs"
  }
}

resource "aws_efs_mount_target" "chromadb" {
  count           = length(var.subnet_ids)
  file_system_id  = aws_efs_file_system.chromadb.id
  subnet_id       = var.subnet_ids[count.index]
  security_groups = var.security_group_ids
}

resource "aws_efs_access_point" "chromadb" {
  file_system_id = aws_efs_file_system.chromadb.id
  root_directory {
    path = "/chroma"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  posix_user {
    gid = 1000
    uid = 1000
  }

  tags = {
    Name = "${var.environment}-chromadb-ap"
  }
}

output "file_system_id" {
  value = aws_efs_file_system.chromadb.id
}

output "mount_target_ids" {
  value = aws_efs_mount_target.chromadb[*].id
}

output "chromadb_access_point_id" {
  value = aws_efs_access_point.chromadb.id
}
