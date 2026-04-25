# Migration Guide: ECS Indexer → Lambda Indexer

This guide explains how to migrate from the ECS-based indexer to the AWS Lambda-based indexer.

## 🎯 Benefits

| Aspect | ECS | Lambda |
|--------|-----|--------|
| **Cost** | $34.83/month | $0.25/month |
| **Scaling** | Manual configuration | Automatic |
| **Management** | Requires container management | Fully managed |
| **Pay Model** | Per hour (whether idle or active) | Per invocation |

## 📊 Cost Savings Example

For processing ~1000 documents/month (~40 per day):

**ECS Current:**
```
1 instance × 512 CPU, 1GB
730 hours × $0.04773 = $34.83/month
```

**Lambda New:**
```
~1200-1800 invocations/month
~3 min average execution = 0.05 hrs per invocation
1500 invocations × 0.05 hrs × $0.0000166 per hr = $0.12/month
+ CloudWatch logs: ~$0.10/month
= $0.25/month (99.3% savings)
```

---

## 🚀 Step 1: Build Lambda Deployment Packages

### On Linux/Mac

```bash
cd lambda/
chmod +x build_lambda_package.sh
./build_lambda_package.sh
```

### On Windows

```powershell
cd lambda
.\build_lambda_package.bat
```

This creates:
- `build/zips/lambda_layer.zip` - Dependencies
- `build/zips/indexer_lambda.zip` - Function code

These are automatically copied to `infra/`

---

## 🔄 Step 2: Update Terraform

### Option A: Replace main.tf (Clean Start)

```bash
cd infra/
cp main.tf main_backup.tf              # Backup current
cp ../lambda/terraform_main.tf main.tf # Use Lambda version
cp variables.tf variables_backup.tf    # Backup
cp ../lambda/terraform_variables.tf variables.tf
```

### Option B: Manual Update (Existing Stack)

**In `infra/main.tf`, remove the ECS indexer module:**

```hcl
# REMOVE THIS BLOCK:
# module "indexer" {
#   source = "./modules/ecs"
#   ...
# }

# ADD THIS BLOCK:
module "indexer_lambda" {
  source = "./modules/lambda"

  environment                   = var.environment
  s3_bucket_arn                 = module.s3.bucket_arn
  sqs_queue_arn                 = module.sqs.queue_arn
  chromadb_host                 = module.chromadb.service_endpoint
  chromadb_port                 = 8000
  bedrock_model_arns            = var.bedrock_model_arns
  subnet_ids                    = module.vpc.private_subnet_ids
  security_group_ids            = [module.security.indexer_sg_id]
  lambda_layer_filename         = var.lambda_layer_filename
  lambda_function_filename      = var.lambda_function_filename
  chunk_size                    = var.chunk_size
  chunk_overlap                 = var.chunk_overlap
  memory_size                   = var.lambda_memory_size
  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = var.lambda_reserved_concurrency

  depends_on = [module.chromadb]
}
```

**In `infra/variables.tf`, add Lambda variables:**

```hcl
variable "lambda_layer_filename" {
  type        = string
  default     = "./lambda_layer.zip"
  description = "Path to lambda_layer.zip"
}

variable "lambda_function_filename" {
  type        = string
  default     = "./indexer_lambda.zip"
  description = "Path to indexer_lambda.zip"
}

variable "lambda_memory_size" {
  type        = number
  default     = 1024
  description = "Lambda memory (128-10240 MB)"
}

variable "lambda_timeout" {
  type        = number
  default     = 900
  description = "Lambda timeout in seconds"
}

variable "lambda_reserved_concurrency" {
  type        = number
  default     = null
  description = "Reserved concurrent executions"
}
```

**Update outputs in `infra/main.tf`:**

```hcl
output "indexer_lambda_function_name" {
  description = "Lambda indexer function name"
  value       = module.indexer_lambda.lambda_function_name
}

output "indexer_lambda_function_arn" {
  description = "Lambda indexer function ARN"
  value       = module.indexer_lambda.lambda_function_arn
}

output "indexer_lambda_log_group" {
  description = "CloudWatch log group for Lambda"
  value       = module.indexer_lambda.lambda_log_group
}
```

---

## 🔧 Step 3: Terraform Plan

```bash
cd infra/

# Verify Lambda module syntax
terraform validate

# Review what will change
terraform plan

# Should show:
# - "aws_ecs_service" "indexer" will be destroyed
# - "aws_lambda_function" "indexer" will be created
# - "aws_lambda_event_source_mapping" will be created
```

---

## ⚠️ Step 4: Backup Before Applying

```bash
# Export current state
terraform state pull > terraform.state.backup

# Screenshot/document current metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=indexer \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Average
```

---

## 🚀 Step 5: Apply Changes

```bash
# Apply Terraform
terraform apply

# Should output:
# indexer_lambda_function_name = "prod-indexer"
# indexer_lambda_function_arn = "arn:aws:lambda:..."
# indexer_lambda_log_group = "/aws/lambda/prod-indexer"
```

---

## 📋 Step 6: Verify Migration

### Check Lambda is Running

```bash
# List Lambda functions
aws lambda list-functions --query 'Functions[?FunctionName==`prod-indexer`]'

# Get function details
aws lambda get-function --function-name prod-indexer

# Test invoke
aws lambda invoke \
  --function-name prod-indexer \
  --payload '{}' \
  response.json
cat response.json
```

### Check SQS → Lambda Integration

```bash
# List event source mappings
aws lambda list-event-source-mappings \
  --function-name prod-indexer

# Should show:
# "EventSourceArn": "arn:aws:sqs:..."
# "State": "Enabled"
```

### Test End-to-End

```bash
# 1. Send a test message to SQS
aws sqs send-message \
  --queue-url "https://sqs.us-east-1.amazonaws.com/123456/indexing-queue" \
  --message-body '{
    "document_id": "test-123",
    "filename": "test.pdf",
    "s3_key": "uploads/test-123/test.pdf"
  }'

# 2. Monitor Lambda logs (wait ~5 seconds)
aws logs tail /aws/lambda/prod-indexer --follow

# Should show:
# INFO Processing SQS batch: 1 messages
# INFO Processing document: test-123
# ... or error details if something failed
```

---

## 🔄 Step 7: Clean Up Old ECS Resources

```bash
# Remove old indexer Docker image from ECR (if desired)
aws ecr batch-delete-image \
  --repository-name personal-library-assistant-indexer \
  --image-ids imageTag=latest

# Or keep it as a backup for rollback

# Remove the old indexer ECS service definition (optional)
# Terraform should have already destroyed it
terraform state list | grep indexer_ecs
```

---

## 🚨 Rollback Procedure

If issues occur, rollback is easy:

```bash
# Restore from backup
terraform state push terraform.state.backup

# Or revert to previous main.tf
git checkout main.tf variables.tf

# Re-apply
terraform apply -var="indexer_image=<ECR_URI>"
```

---

## 🔍 Monitoring Lambda Indexer

### CloudWatch Logs

```bash
# View recent logs
aws logs tail /aws/lambda/prod-indexer --follow --since 5m

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/prod-indexer \
  --filter-pattern "ERROR"

# Get metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=prod-indexer \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

### CloudWatch Alarms

```bash
# View alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix prod-indexer-lambda

# Check specific alarm
aws cloudwatch describe-alarms \
  --alarm-names prod-indexer-lambda-errors
```

---

## 📊 Performance Comparison

### ECS Indexer
- Cold start: Already running (always on)
- Latency: ~0.5s per message (processing only)
- Cost: $34.83/month (fixed)
- Scaling: Manual
- Idle waste: $34.83/month (if not indexing)

### Lambda Indexer
- Cold start: 1-3 seconds (first invocation)
- Latency: ~3.5s per message (1-3s cold start + 0.5s processing)
- Cost: $0.25/month
- Scaling: Automatic
- Idle waste: $0

### For High-Throughput Scenarios

If you need faster responses and are indexing continuously:

```hcl
# Increase reserved concurrency
variable "lambda_reserved_concurrency" {
  default = 100  # Keep 100 warm instances
}

# Cost: ~100 instances × 0.000015 per hour = $1.08/month
# But eliminates cold starts
```

---

## 🎯 Optimization Tips

### 1. Increase Memory for Faster Processing

```hcl
# In terraform.tfvars
lambda_memory_size = 2048  # 2GB (faster CPU)

# Cost impact: ~2x memory = ~2x cost
# But execution time may be 1/2 (net neutral or better)
```

### 2. Set Reserved Concurrency

```hcl
lambda_reserved_concurrency = 50

# Keeps 50 instances "warm" to avoid cold starts
# Cost: 50 × 0.0000166 per hour = $7.30/month
# Eliminates cold starts for high-volume indexing
```

### 3. Batch Processing

Update Lambda handler to process multiple messages per invocation:

```python
# Current: batch_size = 1 (1 message per Lambda invocation)
# Optimize: batch_size = 10 (10 messages per invocation)

# Update in terraform/modules/lambda/main.tf:
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  batch_size = 10  # Process up to 10 messages per invocation
}
```

---

## 📝 Checklist

- [ ] Built Lambda packages (`build_lambda_package.sh`)
- [ ] Updated `infra/main.tf` with Lambda module
- [ ] Updated `infra/variables.tf` with Lambda variables
- [ ] Verified Terraform syntax (`terraform validate`)
- [ ] Reviewed plan (`terraform plan`)
- [ ] Backed up current state
- [ ] Applied changes (`terraform apply`)
- [ ] Verified Lambda function created
- [ ] Tested SQS → Lambda integration
- [ ] Uploaded test PDF to verify end-to-end flow
- [ ] Monitored logs during first indexing
- [ ] Verified cost reduction in AWS billing
- [ ] Documented new Lambda monitoring procedures
- [ ] Updated runbooks for team

---

## ❓ FAQ

**Q: What if a Lambda execution times out?**
A: Increase `lambda_timeout` (max 900s) or optimize PDF processing. Large PDFs may need chunking at extraction time.

**Q: Can I revert to ECS?**
A: Yes. Restore from `terraform.state.backup` or revert to previous `main.tf`.

**Q: What about cold starts affecting indexing?**
A: Acceptable for async batch processing. If critical, set `lambda_reserved_concurrency`.

**Q: Do I need to change the backend code?**
A: No. Backend continues to work identically. Only indexer processing changes.

**Q: How do I test locally?**
A: Use `docker-compose up` which still runs ECS indexer locally. Or create a local Lambda test environment.

---

**Migration estimated time: 30 minutes**  
**Rollback time: 5 minutes**  
**Cost savings: $35/month (99.3%)**

