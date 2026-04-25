#!/bin/bash
set -e

echo "🚀 Deploying Personal Library Assistant to AWS..."

# Configuration
ENVIRONMENT=${ENVIRONMENT:-prod}
AWS_REGION=${AWS_REGION:-us-east-1}
TERRAFORM_DIR="./infra"

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform not found. Please install it first."
    exit 1
fi

echo "📋 Configuration:"
echo "  Environment: $ENVIRONMENT"
echo "  Region: $AWS_REGION"

# Create terraform.tfvars
echo "⚙️ Creating terraform.tfvars..."
cat > "$TERRAFORM_DIR/terraform.tfvars" <<EOF
aws_region           = "$AWS_REGION"
environment          = "$ENVIRONMENT"
s3_bucket_name       = "personal-library-pdfs-\${ENVIRONMENT}-\${AWS_ACCOUNT_ID}"
backend_image        = "\${AWS_ACCOUNT_ID}.dkr.ecr.\${AWS_REGION}.amazonaws.com/personal-library-assistant-backend:latest"
indexer_image        = "\${AWS_ACCOUNT_ID}.dkr.ecr.\${AWS_REGION}.amazonaws.com/personal-library-assistant-indexer:latest"
bedrock_model_arns   = [
    "arn:aws:bedrock:$AWS_REGION::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
    "arn:aws:bedrock:$AWS_REGION::foundation-model/amazon.titan-embed-text-v2:0"
]
log_retention_days   = 30
EOF

# Initialize Terraform
echo "🔄 Initializing Terraform..."
cd "$TERRAFORM_DIR"
terraform init

# Validate
echo "✅ Validating Terraform configuration..."
terraform validate

# Plan
echo "📊 Planning deployment..."
terraform plan -out=tfplan

# Apply
echo "🚀 Applying Terraform configuration..."
read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    terraform apply tfplan
    
    echo "✅ Deployment complete!"
    echo ""
    echo "Outputs:"
    terraform output -json | jq '.'
else
    echo "❌ Deployment cancelled"
    rm tfplan
    exit 1
fi

cd ..
