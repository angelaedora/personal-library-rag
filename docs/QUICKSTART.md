# Quick Start Guide

## ⚡ 5-Minute Local Setup

### 1. Prerequisites
```bash
# Install required tools
# - Docker & Docker Compose
# - Python 3.11+
# - Git

# Clone/navigate to project
cd personal-library-assistant
```

### 2. Configure Environment
```bash
# Copy example env file
cp .env.example .env

# For local dev, you only need dummy AWS credentials:
# AWS_ACCESS_KEY_ID=dummy
# AWS_SECRET_ACCESS_KEY=dummy
# (or leave as-is if using AWS credentials for Bedrock)
```

### 3. Start Services
```bash
# Make scripts executable
chmod +x scripts/run_local.sh

# Start everything
./scripts/run_local.sh

# Wait 10 seconds for services to be ready
```

### 4. Access the Application

**Frontend**: http://localhost:3000
**Backend API**: http://localhost:8000/api
**ChromaDB**: http://localhost:8001

---

## 🧪 Quick Test

### Test 1: Upload a Sample PDF

```bash
# Download a sample PDF
curl -L -o sample.pdf https://arxiv.org/pdf/2404.11198.pdf

# Upload via API
curl -X POST http://localhost:8000/api/books/upload \
  -F "file=@sample.pdf"

# Or use the web interface
# 1. Open http://localhost:3000
# 2. Drag & drop a PDF
# 3. Wait for "indexing complete"
```

### Test 2: Ask a Question

```bash
# Via API
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic of this document?",
    "top_k": 5
  }'

# Or use web interface
# 1. Type question in chat box
# 2. Click Send
# 3. View answer + sources
```

### Test 3: Check Backend Health

```bash
curl http://localhost:8000/api/chat/health
# Should return: {"status":"healthy"}
```

---

## 📝 Common Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f indexer
docker-compose logs -f chromadb
```

### Stop Services

```bash
docker-compose down
```

### Restart Single Service

```bash
docker-compose restart backend
```

### View Running Containers

```bash
docker-compose ps
```

---

## 🐛 Troubleshooting

### "Connection refused" Error

```bash
# Wait longer for services to start
docker-compose ps
# All should show "Up"

# If still failing, check logs
docker-compose logs chromadb
docker-compose logs backend
```

### "Bedrock access denied" (if using real AWS creds)

1. Check credentials in `.env`:
   ```bash
   echo $AWS_ACCESS_KEY_ID
   echo $AWS_SECRET_ACCESS_KEY
   ```

2. Verify Bedrock enabled in AWS console

3. Verify region (us-east-1 preferred)

### "File size too large"

- Max file size: 100MB
- Try with smaller PDF

### "No response to query"

1. Ensure document is uploaded (check "Indexing in progress" message)
2. Wait a few seconds for indexing to complete
3. Check logs: `docker-compose logs -f indexer`

---

## 🚀 Next: Deploy to AWS

Once you've tested locally, deploy to AWS:

```bash
# 1. Build Docker images
chmod +x scripts/build_and_push.sh
./scripts/build_and_push.sh

# 2. Deploy infrastructure
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# Follow prompts and enter AWS region
```

See **DEPLOYMENT.md** for detailed instructions.

---

## 📖 Key Files to Review

1. **Backend Logic**: `backend/app/services/rag_service.py`
2. **API Endpoints**: `backend/app/routes/chat.py`
3. **Indexer Loop**: `indexer/app/indexer.py`
4. **Frontend UI**: `frontend/app.js`
5. **Infrastructure**: `infra/main.tf`

---

## 💡 Tips

- **Local development**: Use `docker-compose logs -f` frequently
- **Testing**: Start with small PDFs (<10MB)
- **API testing**: Use cURL or Postman
- **Frontend**: Open browser DevTools for client-side debugging
- **Performance**: Check response times in API responses

---

## 🔗 Resources

- **API Docs**: See `API.md`
- **Full Docs**: See `README.md`
- **Deployment**: See `DEPLOYMENT.md`
- **Architecture**: See ASCII diagram in `README.md`

---

## ✨ You're Ready!

Your production-ready Personal Library Assistant is now running locally. 

Start uploading PDFs and asking questions! 🚀
