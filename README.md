# Enterprise Knowledge Agent Platform (EKAP)

**Tagline**: "Your organization's knowledge, retrieved, reasoned, and governed."

## Overview

EKAP is a production-grade RAG + Agentic system that acts as a knowledge assistant for enterprise teams, combining:

- **Context Engineering**: RAG with LangGraph + Qdrant
- **Multi-Agent Collaboration**: Researcher, Writer, Reviewer agents
- **Evaluation Framework**: RAGAS + synthetic test data
- **Governance**: Guardrails, caching, observability with LangSmith
- **Deployment at scale**: LangGraph Server + Docker

## Architecture

### Multi-Tenancy & Bounded Contexts
- Each business area (Pharmacy, Supply Chain) gets its own Qdrant collection
- Queries are scoped to specific business contexts - no cross-contamination
- Agents explicitly report when information is not found in their bounded context

### Data Sources
- **Confluence**: Business requirements and documentation
- **Firestore/Datastore**: Configuration data
- **GitLab**: Code repositories, wikis, issues

### Hybrid Search
- **Dense search**: Semantic similarity using Gemini embeddings
- **BM25**: Exact keyword matching for error codes, config keys, function names
- **Reciprocal Rank Fusion**: Combines both search strategies

## Prerequisites

- Python 3.11+
- Docker Desktop for Mac
- Google Gemini API key
- Access to Confluence, Firestore, and GitLab (optional for demo)

## Quick Start

### 1. Install uv (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and setup
```bash
cd ~/ai-engineering/ekap
cp .env.example .env
# Edit .env with your API keys and credentials
```

### 3. Start services with Docker
```bash
docker-compose up -d
```

### 4. Run the API locally (development)
```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Qdrant UI: `http://localhost:6333/dashboard`

## Project Structure

```
ekap/
├── app/              # FastAPI application
├── agents/           # LangGraph agent definitions
├── ingestion/        # Data source connectors + change detection
├── vectorstore/      # Qdrant with multi-tenant collections
├── evaluation/       # RAGAS framework
├── core/             # Config, LLM clients, utilities
├── docker/           # Docker configs
├── tests/            # Test suites
├── data/             # Persistent data (Qdrant, cache)
└── pyproject.toml    # uv dependency management
```

## API Endpoints

- `POST /api/v1/query` - Query the knowledge base
- `POST /api/v1/ingest` - Trigger data ingestion
- `GET /api/v1/ingest/{job_id}` - Check ingestion status
- `GET /api/v1/business-areas` - List available business areas
- `POST /api/v1/evaluate` - Run RAGAS evaluation
- `GET /api/v1/health` - Health check

## Development

### Add dependencies
```bash
uv add <package-name>
```

### Run tests
```bash
uv run pytest
```

### Format code
```bash
uv run ruff format .
```

## Configuration

All configuration is managed through environment variables. See `.env.example` for all available options.

Key configurations:
- `GOOGLE_API_KEY`: Google Gemini API key
- `BUSINESS_AREAS`: Comma-separated list of business areas
- `QDRANT_HOST`: Qdrant server host
- Data source credentials (Confluence, Firestore, GitLab)

## License

MIT
