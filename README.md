# Traceback

**Tagline**: "Your organization's knowledge, retrieved, reasoned, and governed."

## Overview

Traceback is a production-grade retrieval + agentic system that acts as a knowledge assistant for enterprise teams, combining:

- **Context Engineering**: Hybrid search and Qdrant vector store
- **Incident Response**: Retrieval dispatcher + incident briefing agents
- **Evaluation Framework**: RAGAS + synthetic test data
- **Governance**: Guardrails, caching, observability with LangSmith
- **Deployment at scale**: Containerized services (FastAPI, Qdrant, Redis)

## Architecture

### Multi-Tenancy & Bounded Contexts
- Each business area you configure gets a dedicated Qdrant collection (`<business_area>_knowledge`)
- Queries are scoped to the requested business context—no cross-contamination
- Agents explicitly report when information is not found inside that context

### Data Sources
- **Confluence**: Requirements and operational documentation
- **Firestore/Datastore**: Configuration data
- **GitLab**: Code, issues, and wikis
- **OpenMetadata** (optional): Data lineage and asset metadata

### Hybrid Search
- **Dense search**: Semantic similarity using Gemini embeddings
- **BM25**: Exact keyword matching for error codes, config keys, function names
- **Reciprocal Rank Fusion**: Combines both search strategies

## Prerequisites

- Python 3.13+
- `uv` package manager (https://docs.astral.sh/uv/)
- Docker Desktop (for local Qdrant + Redis)
- Google Gemini API key
- Optional: Confluence, Firestore, GitLab credentials for real data

## Quick Start

### 1. Install uv (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Create an environment file
```bash
cd ~/ai-engineering/traceback
cp .env.example env.demo
# Edit env.demo with keys and connector mappings
```

Key variables (see also `how_to_deploy.md` for full syntax):
```bash
GOOGLE_API_KEY=your_google_api_key
BUSINESS_AREAS=claims,benefits
SOURCES_CONFIG=\
  claims:confluence(space=CLM,labels=incident),\
  claims:gitlab(project=org/claims-services),\
  claims:openmetadata(service=datahub),\
  benefits:confluence(space=BNF)
RETRIEVER_OVERRIDES=\
  claims:openmetadata=lineage|cohere_rerank,benefits:confluence=bm25|semantic
```

Copy the tenant env file into place when starting a stack:
```bash
cp env.demo .env
```

### 3. Install dependencies
```bash
uv sync --all-extras --dev
```

### 4. Start services with Docker
```bash
docker compose up -d
```

### 5. Run the API locally (development)
```bash
uv run --python 3.13 uvicorn app.main:app --reload
```

The API becomes available at `http://localhost:8000`  
Helpful URLs:
- API docs: `http://localhost:8000/docs`
- Qdrant UI: `http://localhost:6333/dashboard`

## Project Structure

```
traceback/
├── app/              # FastAPI application
├── agents/           # Incident workflow agents
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

- `POST /api/v1/incidents` - Generate incident briefing from error payload
- `POST /api/v1/ingest` - Trigger data ingestion
- `GET /api/v1/ingest/{job_id}` - Check ingestion status
- `GET /api/v1/business-areas` - List available business areas
- `GET /api/v1/health` - Health check

## Development

### Add dependencies
```bash
uv add <package-name>
```

### Run tests
```bash
uv sync --dev
uv run --python 3.13 pytest
```

### Format code
```bash
uv run ruff format .
```

## Configuration

Traceback is configured entirely through environment variables. Use `.env.example` as a template and refer to `how_to_deploy.md` for per-tenant deployment guidance.

Highlights:
- `BUSINESS_AREAS`: Comma-separated list of business areas (tenants)
- `SOURCES_CONFIG`: Defines which sources each business area exposes, e.g.
  `claims:confluence(space=CLM,labels=incident),claims:gitlab(project=org/repo)`
- `RETRIEVER_OVERRIDES`: (optional) override default retriever stack per source, e.g.
  `claims:openmetadata=lineage_graph|cohere_rerank`
- `QDRANT_HOST` / `QDRANT_PORT`: Vector store location

## License

MIT
