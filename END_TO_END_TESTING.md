# End-to-End Testing Guide

This guide walks you through testing the CodeQL integration manually using the actual API endpoints.

## Prerequisites

1. **Start the application**:
   ```bash
   cd /Users/sandeepgogineni/ai-engineering/traceback
   uv run --python 3.13 uvicorn app.main:app --reload --port 8000
   ```

2. **Verify services are running**:
   - Qdrant: Should be running on `localhost:6333`
   - Neo4j (optional): Should be running if you want graph features
   - CodeQL CLI (optional): Should be in PATH if you want to build databases

## Step 1: Check Application Health

```bash
# Health check
curl http://localhost:8000/health | jq

# List business areas
curl http://localhost:8000/api/v1/business-areas | jq
```

Expected: Returns health status and available business areas.

## Step 2: Register a Code Source

Register a code source for analysis:

```bash
curl -X POST http://localhost:8000/api/v1/code-sources/register \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "pharmacy",
    "source_type": "gitlab",
    "path": "org/my-repo",
    "languages": ["python", "java"],
    "name": "My Repository",
    "enabled": true
  }' | jq
```

Expected response:
```json
{
  "source_id": "pharmacy_gitlab_org_my-repo",
  "business_area": "pharmacy",
  "source_type": "gitlab",
  "path": "org/my-repo",
  "languages": ["python", "java"],
  "name": "My Repository",
  "enabled": true,
  "last_analyzed_commit": null,
  "last_analyzed_time": null
}
```

## Step 3: List Registered Sources

```bash
# List all sources
curl http://localhost:8000/api/v1/code-sources | jq

# Filter by business area
curl "http://localhost:8000/api/v1/code-sources?business_area=pharmacy" | jq

# Only enabled sources
curl "http://localhost:8000/api/v1/code-sources?enabled_only=true" | jq
```

## Step 4: Get Specific Source

```bash
# Replace SOURCE_ID with the actual source_id from step 2
curl http://localhost:8000/api/v1/code-sources/pharmacy_gitlab_org_my-repo | jq
```

## Step 5: Trigger Code Analysis

**Note**: This will only work if CodeQL CLI is installed and Neo4j is configured.

```bash
# Analyze a specific source
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "pharmacy_gitlab_org_my-repo"
  }' | jq

# Or analyze all sources for a business area
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "pharmacy"
  }' | jq
```

Expected response:
```json
{
  "job_id": "uuid-here",
  "status": "running",
  "message": "Analysis started for source pharmacy_gitlab_org_my-repo",
  "business_area": null,
  "source_id": "pharmacy_gitlab_org_my-repo"
}
```

**If CodeQL is not enabled**, you'll get:
```json
{
  "detail": "CodeQL not enabled for business area: pharmacy"
}
```

## Step 6: Test Incident Workflow with Graph Retriever

Test the incident endpoint with graph retriever:

```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "pharmacy",
    "query": "FunctionNotFoundError in process_data",
    "incident_payload": {
      "error": "FunctionNotFoundError",
      "function": "process_data",
      "service": "data-pipeline",
      "timestamp": "2025-11-21T12:00:00Z"
    },
    "retrieval_plan": {
      "sources": ["codeql"],
      "limit": 5
    }
  }' | jq
```

This will:
1. Query the graph retriever (if Neo4j is available)
2. Find functions matching "process_data"
3. Get callers/callees
4. Include graph context in the briefing

Expected response:
```json
{
  "briefing_summary": "...",
  "briefing_markdown": "# Incident Briefing\n\n...",
  "incident_context": {
    "sources": [...],
    "documents": [...]
  },
  "attachments": [...],
  "errors": []
}
```

## Step 7: Check Storage

Check if CodeQL databases were created:

```bash
# List databases in storage
ls -la data/codeql-databases/

# Check registry file
cat data/code_source_registry.json | jq
```

## Step 8: Test Graph Queries (if Neo4j is available)

If you have Neo4j running, you can query it directly:

```bash
# Connect to Neo4j (if running in Docker)
docker exec -it neo4j cypher-shell -u neo4j -p password

# Or use Neo4j Browser at http://localhost:7474
```

Example Cypher queries:
```cypher
// List all functions
MATCH (f:Function)
RETURN f.name, f.business_area, f.repo
LIMIT 10;

// Find callers of a function
MATCH (caller:Function)-[:CALLS]->(callee:Function {name: "process_data"})
WHERE caller.business_area = "pharmacy"
RETURN caller.name, callee.name;

// Find subprocess calls
MATCH (func)-[:RUNS_SUBPROCESS]->(script:Script)
WHERE func.business_area = "pharmacy"
RETURN func.name, script.path;
```

## Step 9: Clean Up

Delete test sources:

```bash
# Delete a source
curl -X DELETE http://localhost:8000/api/v1/code-sources/pharmacy_gitlab_org_my-repo | jq
```

## Troubleshooting

### CodeQL CLI Not Found
```bash
# Check if CodeQL is in PATH
which codeql

# Or set CODEQL_PATH
export CODEQL_PATH=/path/to/codeql
```

### Neo4j Not Available
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Or check connection
curl http://localhost:7474
```

### No Sources Configured
```bash
# Check your .env file
cat .env | grep SOURCES_CONFIG

# Or check via API
curl http://localhost:8000/api/v1/business-areas | jq
```

## Example: Complete Workflow

Here's a complete example workflow:

```bash
#!/bin/bash

# 1. Register source
SOURCE_ID=$(curl -s -X POST http://localhost:8000/api/v1/code-sources/register \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "pharmacy",
    "source_type": "gitlab",
    "path": "org/test-repo",
    "languages": ["python"],
    "enabled": true
  }' | jq -r '.source_id')

echo "Registered source: $SOURCE_ID"

# 2. List sources
echo "Listing sources:"
curl -s http://localhost:8000/api/v1/code-sources | jq '.sources[] | {source_id, path, enabled}'

# 3. Trigger analysis (if CodeQL enabled)
echo "Triggering analysis:"
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d "{\"source_id\": \"$SOURCE_ID\"}" | jq -r '.job_id')

echo "Analysis job: $JOB_ID"

# 4. Test incident workflow
echo "Testing incident workflow:"
curl -s -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "pharmacy",
    "query": "test error",
    "incident_payload": {"error": "test"},
    "retrieval_plan": {"sources": ["codeql"], "limit": 5}
  }' | jq '.briefing_summary'

# 5. Clean up
echo "Cleaning up:"
curl -s -X DELETE http://localhost:8000/api/v1/code-sources/$SOURCE_ID | jq
```

## Using the FastAPI Interactive Docs

You can also test using the interactive API documentation:

1. Start the server:
   ```bash
   uv run --python 3.13 uvicorn app.main:app --reload
   ```

2. Open browser: http://localhost:8000/docs

3. Test endpoints interactively:
   - Expand `/api/v1/code-sources/register`
   - Click "Try it out"
   - Fill in the request body
   - Click "Execute"
   - See the response

## Monitoring

Check application logs for detailed information:

```bash
# Watch logs in real-time
tail -f logs/app.log  # if logging to file

# Or check console output when running uvicorn
```

Look for:
- Source registration logs
- Analysis progress
- Graph retrieval attempts
- Error messages

## Next Steps

Once basic functionality works:

1. **Install CodeQL CLI** to enable database building
2. **Set up Neo4j** to enable graph queries
3. **Configure SOURCES_CONFIG** in `.env` for auto-registration
4. **Test with real repositories** (clone repos locally first)
5. **Integrate with Cloud Function** for production incident response

