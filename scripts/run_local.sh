#!/bin/bash
set -e

echo "🚀 Starting local development environment..."

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install it first."
    exit 1
fi

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your AWS credentials before proceeding"
    read -p "Press enter to continue..."
fi

# Build images
echo "🔨 Building images..."
docker-compose build

# Start services
echo "🟢 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo "🏥 Checking service health..."
for service in backend chromadb; do
    echo "Checking $service..."
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ $service is healthy"
    else
        echo "⚠️  $service may not be ready yet"
    fi
done

echo ""
echo "✅ Local development environment is ready!"
echo ""
echo "🌐 Access points:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:8000/api"
echo "  ChromaDB: http://localhost:8001"
echo ""
echo "📝 To view logs:"
echo "  docker-compose logs -f backend"
echo "  docker-compose logs -f indexer"
echo "  docker-compose logs -f chromadb"
echo ""
echo "🛑 To stop:"
echo "  docker-compose down"
