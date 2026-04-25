# Deployment Guide

## Prerequisites Checklist

- [ ] AWS Account (new or existing)
- [ ] IAM User with AdministratorAccess (for initial setup)
- [ ] Bedrock access enabled in your region (Claude 3, Titan Embeddings)
- [ ] AWS CLI v2 installed and configured
- [ ] Terraform 1.5+ installed
- [ ] Docker & Docker Compose installed
- [ ] Git installed

## Phase 1: Setup AWS Account

### 1.1 Enable Bedrock Models

```bash
# Navigate to AWS Bedrock console:
# https://console.aws.amazon.com/bedrock/

# Go to Model access
# Enable:
# - Anthropic Claude 3 Sonnet
# - Amazon Titan Embeddings Text v2
```

### 1.2 Create Terraform State Backend (Optional but Recommended)

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://personal-library-terraform-state \
  --region us-east-1 \
  --create-bucket-configuration LocationConstraint=us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket personal-library-terraform-state \
  --versioning-configuration Status=Enabled

# Block public access
aws s3api put-public-access-block \
  --bucket personal-library-terraform-state \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Create DynamoDB table for state lock
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 1.3 Create IAM Role for Terraform

```bash
# Create trust policy file
cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::ACCOUNT_ID:user/USERNAME"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Replace ACCOUNT_ID and USERNAME above

# Create role
aws iam create-role \
  --role-name terraform-deploy-role \
  --assume-role-policy-document file:///tmp/trust-policy.json

# Attach policy
aws iam attach-role-policy \
  --role-name terraform-deploy-role \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

## Phase 2: Build & Push Docker Images

### 2.1 Authenticate Docker with ECR

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1

# Login
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

### 2.2 Run Build Script

```bash
cd personal-library-assistant
chmod +x scripts/build_and_push.sh
./scripts/build_and_push.sh
```

This will:
1. Create ECR repositories
2. Build backend image
3. Build indexer image
4. Push to ECR

Note image URIs for next step.

## Phase 3: Deploy Infrastructure with Terraform

### 3.1 Initialize Terraform

```bash
cd infra

# Initialize with S3 backend (optional)
terraform init \
  -backend-config="bucket=personal-library-terraform-state" \
  -backend-config="key=prod/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="encrypt=true" \
  -backend-config="dynamodb_table=terraform-state-lock"

# Or without backend
terraform init
```

### 3.2 Create terraform.tfvars

```bash
cat > terraform.tfvars <<EOF
aws_region = "us-east-1"
environment = "prod"
vpc_cidr = "10.0.0.0/16"

public_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]
azs = ["us-east-1a", "us-east-1b"]

s3_bucket_name = "personal-library-pdfs-prod-${AWS_ACCOUNT_ID}"
sqs_queue_name = "indexing-queue"

backend_image = "${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/personal-library-assistant-backend:latest"
indexer_image = "${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/personal-library-assistant-indexer:latest"

bedrock_model_arns = [
  "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
  "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
]

log_retention_days = 30
EOF

# Replace AWS_ACCOUNT_ID
```

### 3.3 Plan & Apply

```bash
# Validate
terraform validate

# Plan (review resources)
terraform plan -out=tfplan

# Apply
terraform apply tfplan

# Save outputs
terraform output -json > outputs.json
```

This will take ~10-15 minutes.

## Phase 4: Configure Application Load Balancer

### 4.1 Get ALB DNS

```bash
export ALB_DNS=$(terraform output -raw alb_dns_name 2>/dev/null || \
  aws elbv2 describe-load-balancers \
  --query 'LoadBalancers[?Name==`personal-library-alb`].DNSName' \
  --output text)

echo "ALB DNS: $ALB_DNS"
```

### 4.2 Point Domain (Optional)

```bash
# Create Route53 record
aws route53 change-resource-record-sets \
  --hosted-zone-id <ZONE_ID> \
  --change-batch file:///dev/stdin <<EOF
{
  "Changes": [
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "library.example.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "$ALB_DNS",
          "EvaluateTargetHealth": false
        }
      }
    }
  ]
}
EOF
```

## Phase 5: Verify Deployment

### 5.1 Check ECS Services

```bash
# List running tasks
aws ecs list-tasks --cluster prod-cluster
aws ecs describe-tasks \
  --cluster prod-cluster \
  --tasks <task-arn>
```

### 5.2 Check CloudWatch Logs

```bash
# View recent logs
aws logs tail /ecs/prod --follow --since 5m

# Search for errors
aws logs filter-log-events \
  --log-group-name /ecs/prod \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s)000 - 3600000))
```

### 5.3 Test API Health

```bash
curl http://$ALB_DNS/api/chat/health
# Expected: {"status":"healthy","service":"personal-library-backend"}
```

### 5.4 Test Upload Endpoint

```bash
# Create dummy PDF for testing
echo "test" > test.txt

curl -X POST http://$ALB_DNS/api/books/upload \
  -F "file=@test.pdf" \
  -v
```

## Phase 6: Configure Custom Domain & TLS (Optional)

### 6.1 Request ACM Certificate

```bash
# Request certificate
CERT_ARN=$(aws acm request-certificate \
  --domain-name library.example.com \
  --subject-alternative-names www.library.example.com \
  --validation-method DNS \
  --query 'CertificateArn' \
  --output text)

echo "Certificate ARN: $CERT_ARN"
```

### 6.2 Validate Certificate

Follow AWS email or DNS validation prompts in ACM console.

### 6.3 Update ALB Listener (Post-Manual)

```bash
# Update listener to use HTTPS
aws elbv2 modify-listener \
  --listener-arn <listener-arn> \
  --protocol HTTPS \
  --certificates CertificateArn=$CERT_ARN
```

## Monitoring & Operations

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f indexer

# AWS Production
aws logs tail /ecs/prod --follow
```

### Scale Services

```bash
# Update Terraform variable
sed -i 's/desired_count = 2/desired_count = 4/' infra/main.tf

# Apply
cd infra && terraform apply
```

### Stop & Cleanup

```bash
# Destroy infrastructure (WARNING: Deletes all data!)
cd infra && terraform destroy -auto-approve

# Or scale down to 0 to save costs:
terraform apply -var="backend_desired_count=0" -var="indexer_desired_count=0"
```

## Troubleshooting Deployment

### Issue: "Bedrock access denied"

**Solution:**
1. Check IAM role has `bedrock:InvokeModel`
2. Verify Bedrock enabled in console
3. Check region matches (not available in all regions)

### Issue: "ChromaDB connection timeout"

**Solution:**
1. Verify ECS task is running: `aws ecs describe-tasks`
2. Check security groups allow traffic
3. Review CloudWatch logs for startup errors

### Issue: "SQS queue URL not found"

**Solution:**
1. Verify SQS queue created: `aws sqs list-queues`
2. Get URL: `aws sqs get-queue-url --queue-name indexing-queue`
3. Update environment variables

### Issue: Terraform state lock stuck

**Solution:**
```bash
# Release lock
aws dynamodb delete-item \
  --table-name terraform-state-lock \
  --key '{"LockID":{"S":"prod/terraform.tfstate"}}'
```

## Cost Optimization

### Development

- Use `t3.micro` for backend (not Fargate)
- Disable container insights
- Set log retention to 7 days

### Production

- Use Fargate Spot for non-critical services
- Enable CloudFront caching for frontend
- Archive old logs to Glacier

### Monitoring Costs

```bash
# Get daily costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

## Disaster Recovery

### Backup ChromaDB

```bash
# Create EBS snapshot
aws ec2 create-snapshot \
  --volume-id <efs-volume-id> \
  --description "ChromaDB backup"
```

### Restore from Backup

```bash
# Create volume from snapshot
aws ec2 create-volume \
  --snapshot-id <snapshot-id> \
  --availability-zone us-east-1a
```

## Next Steps

1. **Monitor**: Set up CloudWatch alarms for errors
2. **Scale**: Configure auto-scaling based on metrics
3. **Security**: Rotate secrets and enable MFA
4. **Backup**: Schedule regular EFS snapshots
5. **Documentation**: Update runbooks for your team
