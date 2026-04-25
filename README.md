# Personal Library Assistant

A production-grade, cloud-native **Retrieval-Augmented Generation (RAG)** application that allows users to upload PDFs and ask questions grounded in their document library.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          FRONTEND                               │
│         (Static HTML/JS - S3 + CloudFront)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS LOAD BALANCER                            │
│                  (Public → Private Subnets)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   ┌─────────┐         ┌──────────┐         ┌────────┐
   │ Backend │         │ Backend  │         │Indexer│
   │ (ECS #1)│         │ (ECS #2) │         │(ECS)  │
   └────┬────┘         └────┬─────┘         └───┬───┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                    ┌──────────────────┐
                    │   ChromaDB       │
                    │  (ECS + EFS)     │
                    └─────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   ┌─────────┐         ┌─────────┐         ┌────────┐
   │   S3    │         │   SQS   │         │Bedrock│
   │ (PDFs)  │         │(Indexing)         │(LLM)  │
   └─────────┘         └─────────┘         └────────┘
```

### Key Components

- **Frontend**: Static SPA (HTML/CSS/JS) with modern chat UI
- **Backend**: FastAPI service with async RAG pipeline
- **Indexer**: ECS worker that processes PDFs and updates ChromaDB
- **ChromaDB**: Self-hosted vector database on ECS with EFS persistence
- **AWS Services**: S3 (PDFs), SQS (async tasks), Bedrock (LLM/embeddings), IAM (security)
- **Networking**: Private VPC, NAT gateways for egress

## Quick Start (Local Development)

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- AWS credentials configured (for Bedrock access)

### Setup

```bash
# 1. Clone and setup
git clone <repo>
cd personal-library-assistant
cp .env.example .env

# 2. Update .env with your AWS credentials
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - SQS_INDEXING_QUEUE_URL (leave blank for local dev)

# 3. Start services
chmod +x scripts/run_local.sh
./scripts/run_local.sh
```

### Access

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api
- **ChromaDB Admin**: http://localhost:8001

## How It Works

### Document Upload & Indexing Flow

```
1. User uploads PDF via frontend
   ↓
2. Backend validates and generates document_id
   ↓
3. Backend queues task to SQS with s3_key
   ↓
4. Indexer worker polls SQS
   ↓
5. Indexer downloads PDF from S3
   ↓
6. PDF → Text extraction (pdfplumber)
   ↓
7. Text → Chunks (token-aware, with overlap)
   ↓
8. Chunks → Embeddings (Bedrock Titan)
   ↓
9. Embeddings + Metadata → ChromaDB
   ↓
10. Status: "Indexing complete"
```

### Query & RAG Flow

```
1. User submits question via chat
   ↓
2. Backend generates query embedding (Bedrock)
   ↓
3. ChromaDB cosine-similarity search (top-K)
   ↓
4. Retrieved chunks assembled into context
   ↓
5. RAG prompt constructed:
   - Reference documents
   - Chat history
   - User question
   ↓
6. Bedrock Claude 3 generates answer
   ↓
7. Response + source citations returned
   ↓
8. Frontend displays answer and sources
```

## API Endpoints

### Chat

```http
POST /api/chat/query
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "What is...?"},
    {"role": "assistant", "content": "..."}
  ],
  "query": "Tell me more about X",
  "top_k": 5
}

Response:
{
  "answer": "Based on the documents...",
  "sources": [
    {
      "document_id": "uuid",
      "filename": "paper.pdf",
      "page_number": 3,
      "relevance_score": 0.92
    }
  ],
  "retrieval_time_ms": 245,
  "generation_time_ms": 1200,
  "model_used": "anthropic.claude-3-sonnet-20240229-v1:0"
}
```

### Document Management

```http
POST /api/books/upload
Content-Type: multipart/form-data

file: <PDF binary>

Response:
{
  "document_id": "uuid",
  "filename": "paper.pdf",
  "status": "indexing_queued",
  "s3_key": "uploads/uuid/paper.pdf"
}
```

```http
GET /api/books/list
Response: { "documents": [...], "total": 42 }

DELETE /api/books/{document_id}
Response: { "document_id": "uuid", "chunks_deleted": 127 }
```

## Deployment to AWS

### Prerequisites

- AWS Account with:
  - Bedrock access (Claude 3, Titan Embeddings)
  - IAM permissions for Terraform
  - EC2 Classic disabled (for VPC)
- Terraform 1.5+
- AWS CLI v2

### Step 1: Build & Push Docker Images

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

chmod +x scripts/build_and_push.sh
./scripts/build_and_push.sh
```

### Step 2: Deploy Infrastructure

```bash
export ENVIRONMENT=prod
export AWS_REGION=us-east-1

chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

This will:
1. Create VPC with private/public subnets
2. Deploy ECS cluster with Fargate
3. Launch ChromaDB on ECS with EFS
4. Deploy Backend and Indexer services
5. Configure S3, SQS, IAM
6. Set up security groups (strict, VPC-only access)

### Step 3: Update DNS

Point your domain to the Application Load Balancer:

```bash
aws elbv2 describe-load-balancers \
  --query 'LoadBalancers[0].DNSName' \
  --output text
```

## Configuration

### Environment Variables

See `.env.example` for full reference.

**Critical for production:**

```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
CHROMADB_HOST=chromadb-service.internal
S3_BUCKET_NAME=personal-library-pdfs-prod
SQS_INDEXING_QUEUE_URL=https://sqs.xxx
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

### Scaling

**Backend Service:**
- Default: 2 instances
- Adjust via Terraform: `backend_desired_count`
- Metric: Query latency, request volume

**Indexer Service:**
- Default: 1 instance
- Increase for large-scale PDF ingestion
- Monitor SQS queue depth

**ChromaDB:**
- Persistent storage via EFS
- Auto-scaling disabled (stateful service)
- Monitor disk usage

## Security

### Network

- ✅ Private VPC (no internet ingress)
- ✅ NAT gateways for egress
- ✅ Security groups (least privilege)
- ✅ No public database access

### Data

- ✅ S3 bucket encryption (AES-256)
- ✅ S3 versioning enabled
- ✅ 30-day automatic deletion of old versions
- ✅ IAM roles with minimal permissions
- ✅ No hardcoded secrets

### Access

- ✅ Bedrock authentication via IAM
- ✅ SQS/S3 signed requests
- ✅ CloudWatch logging (30-day retention)

## Performance Optimizations

### RAG Pipeline

- **Token-aware chunking**: Respects context window limits
- **Cosine similarity**: Fast vector search in ChromaDB
- **Embedding caching**: Bedrock results reused
- **Async processing**: Non-blocking SQS workers

### Infrastructure

- **ECS Fargate Spot**: Cost optimization (available in main module)
- **CloudWatch Container Insights**: Performance monitoring
- **Multi-AZ**: High availability

## Monitoring & Logging

### CloudWatch Logs

```bash
# Backend logs
aws logs tail /ecs/prod --follow

# Indexer logs
aws logs tail /ecs/prod --follow --log-stream-names indexer

# Specific error
aws logs filter-log-events \
  --log-group-name /ecs/prod \
  --filter-pattern "ERROR"
```

### Metrics

- **Backend**: Request latency, error rate, SQS queue depth
- **Indexer**: Documents processed, embedding time, failures
- **ChromaDB**: Query time, disk usage, memory pressure

## Cost Estimates (Monthly, us-east-1)

| Component | Config | Cost |
|-----------|--------|------|
| ECS Fargate | 3 tasks (backend×2 + indexer) | ~$90 |
| CloudWatch | Logs + Container Insights | ~$15 |
| S3 | 1GB PDFs + versioning | ~$1 |
| SQS | 100K indexing tasks | ~$0.40 |
| Data Transfer | Egress to Bedrock | ~$5 |
| EFS | 100GB ChromaDB storage | ~$30 |
| **Total** | | **~$141** |

*Actual costs depend on usage patterns. Bedrock is charged per token.*

## Troubleshooting

### "ChromaDB connection refused"

```bash
# Check if ChromaDB is running
docker-compose ps

# View logs
docker-compose logs chromadb

# Restart
docker-compose restart chromadb
```

### "Bedrock access denied"

1. Verify AWS credentials in `.env`
2. Check IAM role has `bedrock:InvokeModel`
3. Ensure Bedrock is available in your region

### "SQS messages not processing"

```bash
# Check queue URL
aws sqs get-queue-url --queue-name indexing-queue

# Check for visibility timeout issues
aws sqs receive-message --queue-url <url> --max-number-of-messages 10

# Purge if stuck
aws sqs purge-queue --queue-url <url>
```

## Project Structure

```
personal-library-assistant/
├── backend/                    # FastAPI service
│   ├── app/
│   │   ├── core/              # Config, logging, models
│   │   ├── services/          # RAG, Bedrock, vector store
│   │   ├── routes/            # API endpoints (chat, books)
│   ├── main.py                # App entry point
│   ├── requirements.txt
│   └── Dockerfile
├── indexer/                    # ECS worker
│   ├── app/
│   │   ├── indexer.py         # Main loop
│   │   ├── pdf_parser.py      # PDF extraction
│   │   ├── chunker.py         # Text chunking
│   │   ├── embedder.py        # Embedding generation
│   │   └── vector_writer.py   # ChromaDB writes
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # React SPA
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── infra/                      # Terraform
│   ├── main.tf                # Main orchestration
│   ├── variables.tf
│   ├── modules/
│   │   ├── vpc/               # Networking
│   │   ├── ecs/               # Container orchestration
│   │   ├── s3/                # PDF storage
│   │   ├── sqs/               # Async queue
│   │   ├── efs/               # Persistent storage
│   │   ├── iam/               # Access control
│   │   └── security/          # Security groups
├── scripts/
│   ├── run_local.sh           # Local dev
│   ├── build_and_push.sh      # Docker images
│   └── deploy.sh              # Terraform deployment
├── docker-compose.yml         # Local orchestration
├── .env.example
└── README.md
```

## Contributing

### Code Standards

- **Python**: PEP 8, type hints, 88-char line limit
- **JavaScript**: ES6+, async/await, DOM APIs
- **Terraform**: Modular, tagged resources
- **Commits**: Conventional format (feat:, fix:, refactor:)

### Testing

```bash
# Backend unit tests (TODO: add pytest)
cd backend && python -m pytest

# Indexer tests
cd indexer && python -m pytest

# Frontend integration tests (TODO: add vitest)
```

## Future Enhancements

- [ ] Streaming responses (Server-Sent Events)
- [ ] Hybrid retrieval (vector + BM25 keyword search)
- [ ] Multi-document QA (cross-document reasoning)
- [ ] User authentication & document permissions
- [ ] Document deletion with cleanup
- [ ] Cost analytics dashboard
- [ ] Batch embedding optimization
- [ ] Redis caching for popular queries

## License

MIT

## Support

For issues, feature requests, or questions:

1. Check troubleshooting section above
2. Review CloudWatch logs
3. Open GitHub issue with reproduction steps

---

**Built with production standards in mind. Ready to ship.**
