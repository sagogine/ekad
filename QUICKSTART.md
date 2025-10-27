# EKAP Quick Start Guide

## What We've Built So Far

✅ **Project Structure** - Complete modular architecture with uv dependency management
✅ **Docker Infrastructure** - Qdrant and Redis running in containers
✅ **Core Services** - Configuration, logging, LLM, and embedding services
✅ **Vector Store** - Multi-tenant Qdrant collections for pharmacy and supply_chain
✅ **Hybrid Search** - Dense (vector) + BM25 search with Reciprocal Rank Fusion
✅ **FastAPI Backend** - Basic API with health checks and business area endpoints

## Current Status

### Running Services
- **Qdrant**: http://localhost:6333 (Vector database)
- **Redis**: localhost:6379 (Caching)
- **API**: http://localhost:8000 (FastAPI application)

### API Endpoints Available
- `GET /` - Root endpoint
- `GET /health` - Health check with Qdrant status
- `GET /api/v1/business-areas` - List business areas

### Qdrant Collections Created
- `pharmacy_knowledge` - For pharmacy business area
- `supply_chain_knowledge` - For supply chain business area

## Testing the Setup

```bash
# Check API is running
curl http://localhost:8000/

# Check health status
curl http://localhost:8000/health

# List business areas
curl http://localhost:8000/api/v1/business-areas

# View Qdrant dashboard
open http://localhost:6333/dashboard
```

## Next Steps

We need to implement:

1. **Data Connectors** - Confluence, Firestore, GitLab integrations
2. **Ingestion Pipeline** - Document processing, chunking, embedding generation
3. **RAG Retrieval** - Complete hybrid search with bounded context
4. **Multi-Agent System** - Researcher, Writer, Reviewer agents with LangGraph
5. **Evaluation Framework** - RAGAS integration
6. **API Endpoints** - Query, ingestion, and evaluation endpoints

## Development Commands

```bash
# Start all services
docker-compose up -d

# Start API in development mode
cd ~/ai-engineering/ekap
PYTHONPATH=. uv run uvicorn app.main:app --reload

# Run tests
PYTHONPATH=. uv run python tests/test_setup.py

# Stop all services
docker-compose down

# View logs
docker-compose logs -f
```

## Configuration

Edit `.env` file to add your API keys:
- `GOOGLE_API_KEY` - Required for Gemini LLM and embeddings
- `CONFLUENCE_*` - For Confluence integration
- `GITLAB_TOKEN` - For GitLab integration
- `GOOGLE_APPLICATION_CREDENTIALS` - For Firestore integration

## Project Structure

```
ekap/
├── app/              # FastAPI application
│   └── main.py       # ✅ Entry point with health checks
├── agents/           # LangGraph agents (TODO)
├── ingestion/        # Data connectors (TODO)
├── vectorstore/      # Vector store management
│   ├── qdrant_manager.py      # ✅ Multi-tenant collections
│   └── hybrid_search.py       # ✅ Dense + BM25 search
├── evaluation/       # RAGAS framework (TODO)
├── core/             # Core utilities
│   ├── config.py     # ✅ Configuration management
│   ├── logging.py    # ✅ Structured logging
│   ├── llm.py        # ✅ Gemini LLM client
│   └── embeddings.py # ✅ Embedding service
├── docker/           # Docker configurations
│   └── Dockerfile    # ✅ Application container
├── tests/            # Test suites
│   └── test_setup.py # ✅ Basic connectivity tests
├── data/             # Persistent data
│   ├── qdrant/       # Vector database storage
│   └── cache/        # Redis cache storage
├── docker-compose.yml # ✅ Service orchestration
├── .env              # Environment variables
└── README.md         # Project documentation
```

## Troubleshooting

### Qdrant connection issues
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# View Qdrant logs
docker logs ekap-qdrant

# Restart Qdrant
docker-compose restart qdrant
```

### API not starting
```bash
# Check if port 8000 is in use
lsof -i :8000

# View API logs in the background process
```

### Reset everything
```bash
# Stop all services
docker-compose down -v

# Remove data
rm -rf data/qdrant/* data/cache/*

# Start fresh
docker-compose up -d
PYTHONPATH=. uv run python tests/test_setup.py
```
