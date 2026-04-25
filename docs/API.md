# API Documentation

## Base URL

**Development**: `http://localhost:8000/api`  
**Production**: `https://library.example.com/api`

## Authentication

All endpoints are currently public. For production, implement JWT or OAuth2 in the `core/auth.py` module.

---

## Chat Endpoints

### 1. Query Documents

**Endpoint**: `POST /chat/query`

**Description**: Submit a question and receive RAG-grounded answers with source attribution.

**Request**:

```json
{
  "query": "What are the main findings of this study?",
  "messages": [
    {
      "role": "user",
      "content": "What is machine learning?"
    },
    {
      "role": "assistant",
      "content": "Machine learning is a subset of AI..."
    }
  ],
  "top_k": 5
}
```

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | The user's question |
| `messages` | array | No | Chat history for context |
| `top_k` | integer | No | Number of document chunks to retrieve (1-20, default 5) |

**Response** (200 OK):

```json
{
  "answer": "Based on the documents provided, the main findings include:\n\n1. Significant improvement...",
  "sources": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "research_paper.pdf",
      "page_number": 3,
      "relevance_score": 0.94
    },
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440001",
      "filename": "conference_notes.pdf",
      "page_number": null,
      "relevance_score": 0.87
    }
  ],
  "retrieval_time_ms": 245,
  "generation_time_ms": 1234,
  "model_used": "anthropic.claude-3-sonnet-20240229-v1:0"
}
```

**Error** (400 Bad Request):

```json
{
  "detail": "Invalid request: query cannot be empty"
}
```

**Error** (500 Internal Server Error):

```json
{
  "detail": "Internal server error"
}
```

---

### 2. Health Check

**Endpoint**: `GET /chat/health`

**Description**: Verify API is running.

**Response** (200 OK):

```json
{
  "status": "healthy"
}
```

---

## Document Management Endpoints

### 3. Upload Document

**Endpoint**: `POST /books/upload`

**Description**: Upload a PDF for indexing. File is queued asynchronously.

**Request**:

```
Content-Type: multipart/form-data

file: <binary PDF data>
```

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | file | Yes | PDF file (max 100MB) |

**Response** (200 OK):

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "research_paper.pdf",
  "status": "indexing_queued",
  "s3_key": "uploads/550e8400-e29b-41d4-a716-446655440000/research_paper.pdf"
}
```

**Error** (400 Bad Request):

```json
{
  "detail": "Only PDF files are supported"
}
```

**Error** (413 Payload Too Large):

```json
{
  "detail": "File too large (max 100MB)"
}
```

---

### 4. List Documents

**Endpoint**: `GET /books/list`

**Description**: Retrieve list of indexed documents.

**Query Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `limit` | integer | Max results (default 100) |
| `offset` | integer | Pagination offset (default 0) |

**Response** (200 OK):

```json
{
  "documents": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "research_paper.pdf",
      "upload_timestamp": "2024-01-15T10:30:00Z",
      "page_count": 42,
      "total_chunks": 127,
      "status": "indexed"
    },
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440001",
      "filename": "notes.pdf",
      "upload_timestamp": "2024-01-15T11:00:00Z",
      "page_count": 5,
      "total_chunks": 12,
      "status": "indexing"
    }
  ],
  "total": 2,
  "limit": 100,
  "offset": 0
}
```

---

### 5. Delete Document

**Endpoint**: `DELETE /books/{document_id}`

**Description**: Delete a document and all its indexed chunks.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `document_id` | string | Yes | UUID of document to delete |

**Response** (200 OK):

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunks_deleted": 127
}
```

**Error** (404 Not Found):

```json
{
  "detail": "Document not found"
}
```

---

## Response Models

### ChatMessage

```json
{
  "role": "user | assistant | system",
  "content": "message content"
}
```

### SourceAttribution

```json
{
  "document_id": "uuid",
  "filename": "file.pdf",
  "page_number": 3,
  "relevance_score": 0.92
}
```

### ChatResponse

```json
{
  "answer": "string",
  "sources": [
    {
      "document_id": "string",
      "filename": "string",
      "page_number": "integer | null",
      "relevance_score": "float (0-1)"
    }
  ],
  "retrieval_time_ms": "float",
  "generation_time_ms": "float",
  "model_used": "string"
}
```

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (validation error) |
| 404 | Not Found |
| 413 | Payload Too Large |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Error Handling

All errors follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

### Common Errors

**ChromaDB Connection Error**:
- Message: "Internal server error"
- Solution: Check ChromaDB is running and accessible

**Bedrock Access Error**:
- Message: "Internal server error"
- Solution: Verify AWS credentials and IAM permissions

**S3 Upload Error**:
- Message: "Upload failed"
- Solution: Check S3 bucket exists and IAM role has permissions

---

## Rate Limiting

Currently no rate limiting. For production, implement in middleware:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/chat/query")
@limiter.limit("30/minute")
async def query_documents(request: Request):
    ...
```

---

## Pagination

Implemented in list endpoint:

```python
# Get second page of 20 items
GET /books/list?limit=20&offset=20
```

---

## Filtering

Future enhancement for filtering by document type, upload date, etc.:

```python
# Get documents uploaded after specific date
GET /books/list?created_after=2024-01-01&status=indexed
```

---

## Search Interface Examples

### JavaScript/TypeScript

```javascript
const API_URL = 'http://localhost:8000/api';

async function askQuestion(question) {
  const response = await fetch(`${API_URL}/chat/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: question,
      messages: [],
      top_k: 5,
    }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return await response.json();
}

async function uploadPDF(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_URL}/books/upload`, {
    method: 'POST',
    body: formData,
  });

  return await response.json();
}
```

### Python

```python
import requests

API_URL = "http://localhost:8000/api"

def ask_question(question: str) -> dict:
    response = requests.post(
        f"{API_URL}/chat/query",
        json={
            "query": question,
            "messages": [],
            "top_k": 5,
        },
    )
    response.raise_for_status()
    return response.json()

def upload_pdf(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(
            f"{API_URL}/books/upload",
            files=files,
        )
    response.raise_for_status()
    return response.json()

def list_documents() -> dict:
    response = requests.get(f"{API_URL}/books/list")
    response.raise_for_status()
    return response.json()
```

### cURL

```bash
# Upload PDF
curl -X POST http://localhost:8000/api/books/upload \
  -F "file=@document.pdf"

# Query documents
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic?",
    "top_k": 5
  }'

# List documents
curl http://localhost:8000/api/books/list

# Delete document
curl -X DELETE http://localhost:8000/api/books/550e8400-e29b-41d4-a716-446655440000
```

---

## Performance Considerations

### Retrieval Time

- **Small corpus (<100 documents)**: ~100-300ms
- **Medium corpus (100-1000 documents)**: ~300-800ms
- **Large corpus (>1000 documents)**: ~1-3s

Optimize by increasing `top_k` parameter and using document filters.

### Generation Time

- **Short response (<500 tokens)**: ~800-1500ms
- **Long response (500-1500 tokens)**: ~1500-3000ms
- **Very long response (>1500 tokens)**: ~3000-5000ms

Depends on Bedrock model and workload.

### Total Latency

Typical end-to-end: **2-5 seconds**

---

## Versioning

API is currently **v1** (unversioned). For future versioning:

```
/api/v1/chat/query
/api/v2/chat/query
```

---

## OpenAPI/Swagger

View interactive API docs:

```
http://localhost:8000/docs      # Swagger UI
http://localhost:8000/redoc     # ReDoc
```

JSON schema available at: `/openapi.json`
