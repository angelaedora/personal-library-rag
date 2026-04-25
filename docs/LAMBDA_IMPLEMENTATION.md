# Lambda Indexer: Complete Implementation Guide

## Overview

The Lambda indexer processes PDF documents asynchronously via SQS events, eliminating the need for a continuously running ECS service.

## Architecture

```
S3 Upload (via Backend)
    ↓
SQS Message Queued
    ↓ [Event Source Mapping]
Lambda Indexer Triggered
    ├─ Download PDF from S3
    ├─ Extract text (pdfplumber)
    ├─ Chunk text (token-aware)
    ├─ Generate embeddings (Bedrock)
    ├─ Delete old chunks (idempotent)
    └─ Write to ChromaDB
    ↓
CloudWatch Logs
    ↓
Completion (success or DLQ)
```

## Files Generated

```
lambda/
├── indexer_handler.py              # Main Lambda handler
├── indexer_modules/
│   ├── pdf_parser.py              # PDF text extraction
│   ├── chunker.py                 # Token-aware chunking
│   ├── embedder.py                # Embedding generation
│   ├── bedrock_client.py          # Bedrock API client
│   ├── vector_store.py            # ChromaDB client
│   ├── vector_writer.py           # Chunk persistence
│   └── __init__.py
├── requirements.txt               # Python dependencies
├── build_lambda_package.sh        # Build script (Linux/Mac)
└── build_lambda_package.bat       # Build script (Windows)

infra/
├── modules/lambda/
│   └── main.tf                    # Terraform Lambda module
├── main_with_lambda.tf            # Updated main orchestration
└── variables_with_lambda.tf       # Lambda-specific variables
```

## 📦 Building Lambda Packages

### Automatic Build (Recommended)

**Linux/Mac:**
```bash
cd lambda/
chmod +x build_lambda_package.sh
./build_lambda_package.sh
```

**Windows PowerShell:**
```powershell
cd lambda
.\build_lambda_package.bat
```

**Output:**
```
build/
├── zips/
│   ├── lambda_layer.zip (dependencies)
│   └── indexer_lambda.zip (code)
└── [working directories]
```

### Manual Build (if scripts fail)

```bash
# 1. Create layer structure
mkdir -p lambda_build/python/lib/python3.11/site-packages

# 2. Install dependencies
pip install -r lambda/requirements.txt \
  -t lambda_build/python/lib/python3.11/site-packages/ \
  --platform manylinux2014_x86_64 \
  --only-binary=:all:

# 3. Create layer zip
cd lambda_build
zip -r ../lambda_layer.zip python/
cd ..

# 4. Create function zip
mkdir lambda_func
cp lambda/indexer_handler.py lambda_func/lambda_function.py
cp -r lambda/indexer_modules lambda_func/
cd lambda_func
zip -r ../indexer_lambda.zip .
```

## 🔧 Terraform Deployment

### 1. Prepare Terraform Variables

Create `infra/terraform.tfvars`:

```hcl
aws_region           = "us-east-1"
environment          = "prod"
s3_bucket_name       = "personal-library-pdfs-prod-123456789"

# Lambda-specific
lambda_layer_filename         = "./lambda_layer.zip"
lambda_function_filename      = "./indexer_lambda.zip"
lambda_memory_size            = 1024
lambda_timeout                = 900
lambda_reserved_concurrency   = null  # Or set to 50 for warm instances

backend_image = "123456789.dkr.ecr.us-east-1.amazonaws.com/personal-library-assistant-backend:latest"

bedrock_model_arns = [
  "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
  "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
]
```

### 2. Copy Zip Files to Infra Directory

```bash
# If build script didn't auto-copy:
cp lambda/build/zips/lambda_layer.zip infra/
cp lambda/build/zips/indexer_lambda.zip infra/
```

### 3. Update Main Terraform

Use the provided `main_with_lambda.tf` or manually add:

```bash
# Option A: Replace entire main.tf
cp infra/main_with_lambda.tf infra/main.tf
cp infra/variables_with_lambda.tf infra/variables.tf

# Option B: Manual merge (see MIGRATION_LAMBDA.md)
```

### 4. Initialize & Deploy

```bash
cd infra/

# Validate
terraform validate

# Plan
terraform plan -out=tfplan

# Apply
terraform apply tfplan
```

**Expected output:**
```
Outputs:

indexer_lambda_function_arn = "arn:aws:lambda:us-east-1:123456789:function:prod-indexer"
indexer_lambda_function_name = "prod-indexer"
indexer_lambda_log_group = "/aws/lambda/prod-indexer"
```

## ✅ Verification

### 1. Check Lambda Function

```bash
aws lambda get-function \
  --function-name prod-indexer \
  --region us-east-1
```

### 2. Verify SQS Integration

```bash
aws lambda list-event-source-mappings \
  --function-name prod-indexer
```

Should show:
```json
{
  "EventSourceMappings": [
    {
      "UUID": "...",
      "EventSourceArn": "arn:aws:sqs:us-east-1:...:indexing-queue",
      "FunctionArn": "arn:aws:lambda:us-east-1:...:function:prod-indexer",
      "Enabled": true,
      "BatchSize": 1,
      "State": "Enabled"
    }
  ]
}
```

### 3. Test with Sample PDF

```bash
# 1. Upload a test PDF via backend API
curl -X POST http://localhost:8000/api/books/upload \
  -F "file=@test.pdf"

# 2. Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/123456/indexing-queue" \
  --attribute-names ApproximateNumberOfMessages

# 3. Monitor Lambda logs (wait 5-10 seconds)
aws logs tail /aws/lambda/prod-indexer --follow

# 4. Query the document
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?"}'
```

## 📊 Monitoring & Logging

### CloudWatch Logs

```bash
# View last 50 log events
aws logs tail /aws/lambda/prod-indexer --max-items 50

# Follow logs in real-time
aws logs tail /aws/lambda/prod-indexer --follow

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/prod-indexer \
  --filter-pattern "ERROR"
```

### CloudWatch Metrics

```bash
# Invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=prod-indexer \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum

# Errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=prod-indexer \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum

# Duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=prod-indexer \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Average,Maximum
```

### View Alarms

```bash
# List alarms for Lambda
aws cloudwatch describe-alarms \
  --alarm-name-prefix prod-indexer

# Check specific alarm
aws cloudwatch describe-alarms \
  --alarm-names prod-indexer-lambda-errors
```

## 🔧 Configuration

### Environment Variables

Set in `infra/modules/lambda/main.tf` under `environment`:

```hcl
environment {
  variables = {
    S3_BUCKET         = "personal-library-pdfs"
    CHROMADB_HOST     = "chromadb.internal"
    CHROMADB_PORT     = "8000"
    CHUNK_SIZE        = "1000"
    CHUNK_OVERLAP     = "200"
    LOG_LEVEL         = "INFO"
    AWS_REGION        = "us-east-1"
  }
}
```

### Performance Tuning

**1. Increase Memory for Faster Execution**

```hcl
variable "lambda_memory_size" {
  default = 2048  # 2GB (faster CPU)
}

# Cost impact: ~2x
# Speed improvement: potentially 40-60% faster
```

**2. Keep Instances Warm**

```hcl
variable "lambda_reserved_concurrency" {
  default = 50  # Keep 50 instances warm
}

# Eliminates cold starts
# Cost: ~$7/month
```

**3. Batch Processing**

```hcl
# In event source mapping
batch_size = 10  # Process 10 messages per invocation

# Reduces Lambda invocations
# Better throughput for high-volume indexing
```

## 🚨 Error Handling

### Common Errors

**"Unable to import module 'lambda_function'"**

→ Missing dependencies in layer. Rebuild:
```bash
rm -rf lambda/build
./lambda/build_lambda_package.sh
```

**"Timeout while indexing large PDF"**

→ Increase timeout or memory:
```hcl
lambda_timeout = 900  # Max 15 minutes
lambda_memory_size = 2048  # More CPU = faster
```

**"ChromaDB connection refused"**

→ Verify security groups allow Lambda → ChromaDB
```bash
# Check security group rules
aws ec2 describe-security-groups \
  --group-ids sg-xxxxx
```

**"Access Denied to S3"**

→ Check Lambda IAM role
```bash
aws iam get-role-policy \
  --role-name prod-lambda-indexer-role \
  --policy-name prod-lambda-s3-access
```

### DLQ (Dead Letter Queue)

SQS messages that fail are automatically retried. To prevent infinite retries, configure a DLQ:

```hcl
# In modules/sqs/main.tf
resource "aws_sqs_queue" "indexing_dlq" {
  name = "${var.queue_name}-dlq"
}

resource "aws_sqs_queue" "indexing" {
  # ... existing config ...
  
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.indexing_dlq.arn
    maxReceiveCount     = 3  # Retry 3 times before DLQ
  })
}
```

Monitor DLQ:
```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/123456/indexing-queue-dlq" \
  --attribute-names ApproximateNumberOfMessages
```

## 📈 Cost Analysis

### Pricing Model

```
AWS Lambda Pricing:
- $0.0000002 per request
- $0.0000166667 per GB-second
- Free tier: 1M requests + 400,000 GB-seconds/month

Example (1000 documents/month):
- Invocations: 1000 × $0.0000002 = $0.0002
- Memory: 1GB × 3min × 1000 = 3000 GB-seconds
- Compute: 3000 × $0.0000166667 = $0.05
- Logs: ~$0.10
- Total: ~$0.15/month
```

### Comparison

```
ECS Indexer (current):
- Always running: $34.83/month

Lambda Indexer:
- Pay per execution: $0.15/month

Savings: $34.68/month (99.6%)
```

### With Reserved Concurrency (optional)

```
50 warm instances:
- 50 × 0.0000166667 per hour × 730 hours = $6.10/month
- Plus execution costs: +$0.15/month
- Total: $6.25/month (vs $0.15 without)

Trade-off: Eliminates cold starts for $6/month
```

## 🔄 Updating Lambda Code

To update the Lambda function code:

```bash
# 1. Edit code in lambda/indexer_modules/ or lambda/indexer_handler.py
# 2. Rebuild packages
./lambda/build_lambda_package.sh

# 3. Copy to infra/
cp lambda/build/zips/indexer_lambda.zip infra/

# 4. Redeploy
cd infra/
terraform apply -replace="module.indexer_lambda.aws_lambda_function.indexer"
```

## 📋 Rollback Procedure

If Lambda indexer fails:

```bash
# Restore previous state
terraform state pull > current.state
terraform state push previous.state.backup

# Or manually recreate ECS indexer
cd infra/
terraform apply -var="enable_lambda_indexer=false"
```

## 📚 Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Troubleshooting Lambda Functions](https://docs.aws.amazon.com/lambda/latest/dg/lambda-troubleshooting.html)

## ✅ Checklist

- [ ] Built Lambda packages
- [ ] Updated Terraform files
- [ ] Configured `terraform.tfvars`
- [ ] Copied zip files to `infra/`
- [ ] Ran `terraform validate`
- [ ] Reviewed `terraform plan`
- [ ] Deployed with `terraform apply`
- [ ] Verified Lambda function created
- [ ] Tested SQS → Lambda trigger
- [ ] Tested end-to-end indexing
- [ ] Verified CloudWatch logs
- [ ] Set up alarms
- [ ] Monitored costs
- [ ] Documented for team

