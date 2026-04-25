#!/bin/bash
set -e

# Build Lambda deployment packages for indexer

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
LAYER_DIR="${BUILD_DIR}/layer"
ZIP_DIR="${BUILD_DIR}/zips"

echo "🔨 Building Lambda deployment packages..."

# Create directories
rm -rf "$BUILD_DIR"
mkdir -p "$LAYER_DIR/python/lib/python3.11/site-packages"
mkdir -p "$ZIP_DIR"

# Build Lambda Layer (dependencies)
echo "📦 Building Lambda layer with dependencies..."
pip install -r "${SCRIPT_DIR}/requirements.txt" \
  -t "$LAYER_DIR/python/lib/python3.11/site-packages/" \
  --only-binary=:all: \
  --implementation cp \
  --python-version 311 \
  --platform manylinux2014_x86_64

# Remove unnecessary files from layer
cd "$LAYER_DIR/python/lib/python3.11/site-packages"
rm -rf *.dist-info __pycache__ *.pyc *.pyo
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.so" -delete 2>/dev/null || true

echo "✅ Layer built"

# Create layer zip
cd "$LAYER_DIR"
zip -r "$ZIP_DIR/lambda_layer.zip" . > /dev/null
echo "📦 Layer zip created: lambda_layer.zip ($(du -h $ZIP_DIR/lambda_layer.zip | cut -f1))"

# Build Lambda function code
echo "📝 Building Lambda function code..."
FUNC_BUILD_DIR="${BUILD_DIR}/function"
mkdir -p "$FUNC_BUILD_DIR"

# Copy handler and modules
cp "${SCRIPT_DIR}/indexer_handler.py" "$FUNC_BUILD_DIR/lambda_function.py"
cp -r "${SCRIPT_DIR}/indexer_modules" "$FUNC_BUILD_DIR/"

# Create zip for function code
cd "$FUNC_BUILD_DIR"
zip -r "$ZIP_DIR/indexer_lambda.zip" . > /dev/null
echo "📦 Function zip created: indexer_lambda.zip ($(du -h $ZIP_DIR/indexer_lambda.zip | cut -f1))"

# Display summary
echo ""
echo "✅ Build complete!"
echo ""
echo "Deployment packages created:"
echo "  📦 $ZIP_DIR/lambda_layer.zip"
echo "  📦 $ZIP_DIR/indexer_lambda.zip"
echo ""
echo "Next steps:"
echo "  1. Copy zips to Terraform directory"
echo "  2. Update Terraform with paths"
echo "  3. Run: terraform apply"
echo ""

# Copy to infra directory if it exists
if [ -d "${SCRIPT_DIR}/../infra" ]; then
  echo "📋 Copying to infra directory..."
  cp "$ZIP_DIR/lambda_layer.zip" "${SCRIPT_DIR}/../infra/lambda_layer.zip"
  cp "$ZIP_DIR/indexer_lambda.zip" "${SCRIPT_DIR}/../infra/indexer_lambda.zip"
  echo "✅ Files copied to infra/"
fi
