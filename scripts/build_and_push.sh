#!/bin/bash
set -e

echo "🚀 Building and pushing Docker images..."

AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}
ECR_REPO=${ECR_REPO:-personal-library-assistant}

# Create ECR repositories if they don't exist
echo "📦 Ensuring ECR repositories exist..."
for service in backend indexer chromadb; do
    repo_name="$ECR_REPO-$service"
    if ! aws ecr describe-repositories --repository-names "$repo_name" --region "$AWS_REGION" 2>/dev/null; then
        echo "Creating ECR repository: $repo_name"
        aws ecr create-repository \
            --repository-name "$repo_name" \
            --region "$AWS_REGION" \
            --encryption-configuration encryptionType=AES
    fi
done

# Login to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Build and push backend
echo "🔨 Building backend image..."
docker build -t "$ECR_REPO-backend:latest" ./backend
docker tag "$ECR_REPO-backend:latest" "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO-backend:latest"
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO-backend:latest"

# Build and push indexer
echo "🔨 Building indexer image..."
docker build -t "$ECR_REPO-indexer:latest" ./indexer
docker tag "$ECR_REPO-indexer:latest" "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO-indexer:latest"
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO-indexer:latest"

echo "✅ All images pushed successfully!"
echo "Backend: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO-backend:latest"
echo "Indexer: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO-indexer:latest"
