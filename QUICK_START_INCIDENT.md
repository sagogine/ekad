# Quick Start: Process Your First Incident

## Prerequisites Checklist

- [ ] Traceback application running
- [ ] Qdrant running (vector database)
- [ ] API keys configured in `.env`
- [ ] Data ingested for your business area

## Step-by-Step Execution

### Step 1: Configure Business Area

Edit `.env`:
```bash
BUSINESS_AREAS=cerebro
```

### Step 2: Configure Sources

Edit `.env`:
```bash
SOURCES_CONFIG=cerebro:confluence(space=CEREBRO),\
  cerebro:code(source=gitlab,project_path=your-org/cerebro-repo,languages=python|java|sql),\
  cerebro:openmetadata(service=cerebro-datahub)
```

**Replace:**
- `CEREBRO` → Your actual Confluence space key
- `your-org/cerebro-repo` → Your actual GitLab project path
- `cerebro-datahub` → Your OpenMetadata service name

### Step 3: Add API Keys

Edit `.env` and add:

```bash
# Confluence
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_USERNAME=your-email@company.com
CONFLUENCE_API_TOKEN=your_token_here

# GitLab
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=your_token_here

# OpenMetadata
OPENMETADATA_URL=https://openmetadata.company.com/api/v1
OPENMETADATA_TOKEN=your_token_here
```

### Step 4: Start Services

```bash
# Start Qdrant
docker-compose up -d qdrant

# Start Neo4j (optional, for code graph)
docker-compose up -d neo4j

# Start Traceback
uv run --python 3.13 uvicorn app.main:app --reload --port 8000
```

### Step 5: Ingest Data

```bash
# Trigger ingestion
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "cerebro",
    "sources": ["confluence", "code", "openmetadata"],
    "mode": "full"
  }' | jq

# Check status (use job_id from above)
curl http://localhost:8000/api/v1/ingest/{job_id} | jq
```

**Wait for ingestion to complete** (may take several minutes depending on data size).

### Step 6: Process Your Incident

```bash
# Using the example payload file
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d @example_incident_payload.json | jq '.briefing_markdown' > incident_brief.md

# Or inline
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "cerebro",
    "query": "BigQuery load job failed: CSV processing errors in LOAD00000001.csv.gz",
    "incident_payload": {
      "incident_id": "INC14217264",
      "error_code": "UNKNOWN_ERR",
      "job_name": "ingestion-raw-prd",
      "table": "lt-dia-lake-prd-raw.entity_vendor.cpms_vendors_hist",
      "gcs_path": "gs://cerebro-prd-raw-entity-vendor/CPMS/landing/CPMS.VENDORS/LOAD00000001.csv.gz",
      "csv_error": "Data between close quote character and field separator; line_number: 6242",
      "severity": "critical"
    }
  }' | jq '.briefing_markdown'
```

## What Happens

1. **Query Parsing**: Extracts key terms (table name, job name, error type)
2. **Multi-Source Retrieval**:
   - **Confluence**: Finds documentation about ingestion jobs, BigQuery load processes
   - **Code**: Finds code that handles CSV processing, BigQuery loads
   - **OpenMetadata**: Finds lineage for `cpms_vendors_hist` table, upstream/downstream dependencies
3. **Context Building**: Combines all retrieved information
4. **Briefing Generation**: Creates markdown brief with:
   - Incident summary
   - Relevant documentation
   - Code references
   - Data lineage context
   - Recommended actions

## Expected Output

The response will include a `briefing_markdown` field with:

```markdown
# Incident Briefing

## Summary
BigQuery load job failed for ingestion-raw-prd with CSV processing errors...

## Relevant Documentation
- [Confluence Doc] BigQuery Load Process...
- [Code] CSV processing function in ingestion_handler.py...
- [Lineage] Table cpms_vendors_hist depends on...

## Recommended Actions
1. Check CSV file format at line 6242
2. Verify column TRANSIT_CO_ACCT_N data format
3. Review ingestion job configuration...
```

## Troubleshooting

**"No sources configured"**
- Check `SOURCES_CONFIG` format in `.env`
- Restart application after changing `.env`

**"No documents found"**
- Run ingestion first
- Check API keys are correct
- Verify sources exist (Confluence space, GitLab repo, etc.)

**"Briefing is generic"**
- Ensure data was ingested successfully
- Check ingestion job completed without errors
- Verify sources have relevant content

## Next Steps

1. Review the generated briefing
2. Refine query if needed (more specific = better results)
3. Adjust `retrieval_plan.limit` to get more/fewer documents
4. Use specific `sources` in retrieval_plan to focus on certain types

