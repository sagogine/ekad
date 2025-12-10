# Step-by-Step Setup for Incident Workflow

This guide walks you through setting up Traceback to process real incidents like the Cerebro ingestion failure.

## Step 1: Configure Your Business Area

Edit your `.env` file and set:

```bash
# Business Area Configuration
BUSINESS_AREAS=cerebro

# Or if you have multiple:
BUSINESS_AREAS=cerebro,claims,retail
```

## Step 2: Configure Data Sources

In your `.env` file, configure where to pull data from:

```bash
# Source Configuration
# Format: business_area:source_type(key=value,key2=value2)
SOURCES_CONFIG=cerebro:confluence(space=CEREBRO),\
  cerebro:code(source=gitlab,project_path=your-org/cerebro-repo,languages=python|java|sql),\
  cerebro:openmetadata(service=cerebro-datahub)
```

**Breakdown:**
- `cerebro:confluence(space=CEREBRO)` - Pulls docs from Confluence space "CEREBRO"
- `cerebro:code(...)` - Parses code from GitLab repo
- `cerebro:openmetadata(...)` - Fetches lineage from OpenMetadata

## Step 3: Add API Keys and Credentials

### Confluence API Key

```bash
# Confluence Configuration
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_USERNAME=your-email@company.com
CONFLUENCE_API_TOKEN=your_confluence_api_token_here
```

**How to get Confluence API token:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy the token and paste it in `.env`

### GitLab Token

```bash
# GitLab Configuration
GITLAB_URL=https://gitlab.com  # or your GitLab instance
GITLAB_TOKEN=your_gitlab_personal_access_token_here
```

**How to get GitLab token:**
1. Go to GitLab → Settings → Access Tokens
2. Create token with `read_api` and `read_repository` scopes
3. Copy token and paste in `.env`

### OpenMetadata Token

```bash
# OpenMetadata Configuration
OPENMETADATA_URL=https://your-openmetadata.company.com/api/v1
OPENMETADATA_TOKEN=your_openmetadata_token_here
```

**How to get OpenMetadata token:**
1. Log into OpenMetadata UI
2. Go to Settings → Bots → Create/Edit bot
3. Generate JWT token
4. Copy token and paste in `.env`

## Step 4: Optional - Code Graph (Neo4j)

If you want code relationship analysis:

```bash
# Code Graph Configuration
CODEQL_ENABLED=true
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

## Step 5: Complete .env Example

Here's a complete `.env` file example:

```bash
# ============================================
# REQUIRED
# ============================================
GOOGLE_API_KEY=your_google_api_key_here
BUSINESS_AREAS=cerebro

# ============================================
# SOURCE CONFIGURATION
# ============================================
SOURCES_CONFIG=cerebro:confluence(space=CEREBRO),\
  cerebro:code(source=gitlab,project_path=your-org/cerebro-repo,languages=python|java|sql),\
  cerebro:openmetadata(service=cerebro-datahub)

# ============================================
# CONFLUENCE
# ============================================
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_USERNAME=your-email@company.com
CONFLUENCE_API_TOKEN=your_confluence_api_token

# ============================================
# GITLAB
# ============================================
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your_gitlab_token

# ============================================
# OPENMETADATA
# ============================================
OPENMETADATA_URL=https://openmetadata.company.com/api/v1
OPENMETADATA_TOKEN=your_openmetadata_token

# ============================================
# OPTIONAL: CODE GRAPH
# ============================================
CODEQL_ENABLED=false  # Set to true if using Neo4j
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# ============================================
# INFRASTRUCTURE (Defaults usually fine)
# ============================================
QDRANT_HOST=localhost
QDRANT_PORT=6333
APP_NAME=Traceback
LOG_LEVEL=INFO
```

## Step 6: Start Services

```bash
# Start Qdrant (if not using Docker)
# Or use Docker:
docker-compose up -d qdrant

# Start Neo4j (if using code graph)
docker-compose up -d neo4j
```

## Step 7: Ingest Data

Before processing incidents, you need to ingest your data:

```bash
# Start the application
uv run --python 3.13 uvicorn app.main:app --reload --port 8000

# In another terminal, trigger ingestion
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "cerebro",
    "sources": ["confluence", "code", "openmetadata"],
    "mode": "full"
  }'
```

Wait for ingestion to complete (check status via `/api/v1/ingest/{job_id}`).

## Step 8: Process Your Incident

Now you can process your real incident:

```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "cerebro",
    "query": "BigQuery load job failed for ingestion-raw-prd: CSV processing errors in LOAD00000001.csv.gz",
    "incident_payload": {
      "incident_id": "INC14217264",
      "customer": "Cerebro Event Manager",
      "short_description": "The k8s_container ingestion-raw-prd has failed with error code UNKNOWN_ERR",
      "priority": "Medium",
      "error_code": "UNKNOWN_ERR",
      "error_message": "LOAD00000001.csv.gz-72ab42933a85: Table lt-dia-lake-prd-raw.entity_vendor.cpms_vendors_hist_LOAD00000001_csv_gz_f68191e5-9223-45b9-80fc-72ab42933a85_TEMP load_job has errors",
      "job_name": "ingestion-raw-prd",
      "source_directory": "cerebro-prd-raw-entity-vendor/CPMS/landing/CPMS.VENDORS",
      "table": "lt-dia-lake-prd-raw.entity_vendor.cpms_vendors_hist",
      "gcs_path": "gs://cerebro-prd-raw-entity-vendor/CPMS/landing/CPMS.VENDORS/LOAD00000001.csv.gz",
      "csv_error": "Data between close quote character and field separator; line_number: 6242; column_index: 17; column_name: TRANSIT_CO_ACCT_N",
      "severity": "critical",
      "component_type": "k8s_container"
    },
    "retrieval_plan": {
      "sources": null,
      "limit": 15
    }
  }' | jq '.briefing_markdown'
```

## Step 9: Understanding the Response

The response will include:

1. **briefing_summary** - Short summary for ticket title
2. **briefing_markdown** - Full markdown briefing with:
   - Incident summary
   - Relevant documentation from Confluence
   - Code references from GitLab
   - Data lineage from OpenMetadata (table relationships)
   - Recommended next steps

3. **incident_context** - Raw retrieval results
4. **attachments** - Metadata about sources consulted

## Quick Reference: Where to Find API Keys

| Service | Where to Get Token |
|---------|-------------------|
| **Confluence** | https://id.atlassian.com/manage-profile/security/api-tokens |
| **GitLab** | GitLab → Settings → Access Tokens → Create token |
| **OpenMetadata** | OpenMetadata UI → Settings → Bots → Generate JWT |
| **Google API** | Google Cloud Console → APIs & Services → Credentials |

## Troubleshooting

### "No sources configured for business area"
- Check `SOURCES_CONFIG` in `.env`
- Verify format: `business_area:source(key=value)`
- Restart application after changing `.env`

### "No documents found"
- Run ingestion first: `POST /api/v1/ingest`
- Check ingestion job status
- Verify API keys are correct
- Check application logs for errors

### "Graph retriever not available"
- This is expected if `CODEQL_ENABLED=false`
- System will work without it, just won't have code relationships

## Example: Complete Workflow

```bash
# 1. Configure .env with your keys
# 2. Start services
docker-compose up -d qdrant neo4j

# 3. Start application
uv run --python 3.13 uvicorn app.main:app --reload --port 8000

# 4. Ingest data (wait for completion)
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"business_area": "cerebro", "mode": "full"}'

# 5. Process incident
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d @incident_payload.json | jq '.briefing_markdown' > incident_brief.md
```

## Next Steps

1. ✅ Configure `.env` with your API keys
2. ✅ Set `SOURCES_CONFIG` for your business area
3. ✅ Run ingestion to populate knowledge base
4. ✅ Process your incident
5. ✅ Review and refine briefing quality

