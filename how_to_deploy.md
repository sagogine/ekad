# Deploying Traceback Per Business Area

This guide explains how to run Traceback for multiple customers or domains while keeping data, configuration, and workloads isolated.

---

## 1. Plan Your Tenants

- Decide how you want to segment knowledge (`retail`, `loyalty`, `health`, etc.).
- Give each tenant a unique **business area slug** (lowercase, no spaces). Traceback will create a Qdrant collection named `<business_area>_knowledge`.
- Gather credentials for each data source (Confluence, Firestore, GitLab, …).

---

## 2. Create a Tenant-Specific Environment File

Use `.env.example` as the baseline, then build one file per tenant. Example for a `claims` tenant with documentation + code + lineage:

```bash
cp .env.example env.retail
```

Edit `env.retail` and set the following:

```bash
# Required
GOOGLE_API_KEY=your_google_api_key
BUSINESS_AREAS=claims

# Source configuration (preferred)
SOURCES_CONFIG=claims:confluence(space=CLM,labels=incident),\
  claims:code(source=gitlab,project_path=org/claims-pipelines,languages=python|java|sql),\
  claims:openmetadata(service=datahub)

# Retriever overrides (optional)
RETRIEVER_OVERRIDES=claims:code=code,claims:openmetadata=lineage

# Legacy credentials (still supported; used when SOURCES_CONFIG is absent)
CONFLUENCE_URL=https://your-domain.atlassian.net
CONFLUENCE_USERNAME=bot@company.com
CONFLUENCE_API_TOKEN=xxx

GOOGLE_CLOUD_PROJECT=project-name
GOOGLE_APPLICATION_CREDENTIALS=/secrets/claims-sa.json

GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=xxx

# OpenMetadata Configuration
OPENMETADATA_URL=https://openmetadata.company.com/api/v1
OPENMETADATA_TOKEN=your_openmetadata_api_token
```

### Configuration Notes

**OpenMetadata Configuration:**
- `OPENMETADATA_URL`: The base URL for your OpenMetadata API (defaults to `http://localhost:8585/api/v1` if not set)
- `OPENMETADATA_TOKEN`: API authentication token (optional, but required for authenticated endpoints)
- The connector uses these environment variables by default, but you can override them per-source in `SOURCES_CONFIG`:
  ```bash
  claims:openmetadata(service=datahub,api_url=https://custom-url.com/api/v1,api_token=custom_token)
  ```

**Code Connector Configuration:**
- The code connector parses SQL/Python/Java files into logical units (functions, classes, SQL statements)
- Configure via `SOURCES_CONFIG`:
  ```bash
  claims:code(source=gitlab,project_path=org/repo,languages=python|java|sql)
  ```
- `source`: Currently supports `gitlab` (default)
- `project_path`: GitLab project path (e.g., `org/repo`)
- `languages`: Pipe-separated list of languages to parse (default: `python|java|sql`)

**Retriever Configuration:**
- Default mappings: `gitlab` → `code`, `openmetadata` → `lineage`, `confluence`/`firestore` → `docs`
- Override via `RETRIEVER_OVERRIDES`:
  ```bash
  RETRIEVER_OVERRIDES=claims:code=code,claims:openmetadata=lineage
  ```

**Secrets Manager Configuration (Optional):**
- Traceback supports fetching secrets from GCP Secret Manager as a fallback when environment variables are not set
- Priority: Environment variables → GCP Secret Manager → None
- To enable GCP Secret Manager:
  ```bash
  SECRETS_PROVIDER=gcp
  SECRETS_PATH_PREFIX=traceback/prod  # Optional: prefix for secret names
  GOOGLE_CLOUD_PROJECT=your-gcp-project-id
  ```
- Secret names in GCP Secret Manager should match field names converted to kebab-case:
  - `google-api-key` (for `GOOGLE_API_KEY`)
  - `gitlab-token` (for `GITLAB_TOKEN`)
  - `confluence-api-token` (for `CONFLUENCE_API_TOKEN`)
  - etc.
- With `SECRETS_PATH_PREFIX=traceback/prod`, secrets would be: `traceback/prod/google-api-key`, `traceback/prod/gitlab-token`, etc.
- **Note:** GCP Secret Manager requires proper authentication (service account JSON or default credentials)

Repeat the process for each tenant. You can point multiple business areas to the same Traceback instance if they share infrastructure, but **per-tenant `.env` files keep deployments clean and isolated**.

---

## 3. Start an Instance

Pick the tenant you want to launch and export its env file:

```bash
cd /Users/sandeepgogineni/ai-engineering/traceback

export ENV_FILE=env.retail
cp "$ENV_FILE" .env

docker compose up -d
```

Alternatively, mount the env file directly:

```bash
ENV_FILE=env.retail docker compose up -d
```

> **Tip:** when running multiple tenants on the same host, override ports in `docker-compose.yml` (or duplicate the file) so each API listens on a unique port.

---

## 4. Initialize the Tenant

1. Wait for the stack to start: `docker compose ps`.
2. Verify health: `curl http://localhost:8000/health`.
3. Initialize collections (optional—the API does this lazily):

   ```bash
   docker compose exec api uv run python -c "from vectorstore.qdrant_manager import qdrant_manager; qdrant_manager.initialize_collections()"
   ```

4. Trigger ingestion when ready:

   ```bash
   curl -X POST http://localhost:8000/api/v1/ingest \
     -H "Content-Type: application/json" \
     -d '{
       "business_area": "claims",
       "sources": ["confluence", "code", "openmetadata"],
       "mode": "incremental"
     }'
   ```

   Note: Use `code` instead of `gitlab` if you want parsed code units, or `openmetadata` for lineage ingestion.

---

## 5. Deploying Multiple Tenants

### Option A – Separate Compose Stacks

Run one `docker compose` stack per tenant, each in its own directory:

```
traceback-retail/
  docker-compose.yml (override ports to 8100/6433/etc.)
  env.retail -> .env
traceback-loyalty/
  docker-compose.yml (override ports to 8200/6533/etc.)
  env.loyalty -> .env
```

Pros: easy to reason about; no cross-contamination.  
Cons: more containers to manage.

### Option B – Orchestrator (Kubernetes / ECS / Nomad)

- Package the API as a container.
- Use Helm or Terraform to template:
  - `ConfigMap`/`Secret` per tenant (provides business areas and connector keys).
  - Deployment + Service per tenant with unique DNS (e.g. `retail-traceback.company.com`).
  - One shared Qdrant/Redis cluster or dedicated per tenant.

Pros: scalable, declarative provisioning.  
Cons: requires platform tooling.

---

## 6. Lifecycle Operations

- **Update code**: rebuild the image and redeploy (`docker compose up --build -d` or new container image tag).
- **Rotate credentials**: update the tenant’s env/secret and restart the API service.
- **Backup data**: snapshot the Qdrant volumes (`volume: qdrant_data_<tenant>`). Each tenant’s data lives in its own collection.
- **Tear down a tenant**: stop the stack and delete volumes; remove corresponding collections with `qdrant_manager`.

---

## 7. Checklist Per Tenant

- [ ] `.env` created with `BUSINESS_AREAS` set.
- [ ] Connector mappings defined via `SOURCES_CONFIG` (or legacy envs for backwards compatibility).
- [ ] Secrets stored securely (Vault, AWS Secrets Manager, etc.).
- [ ] Docker compose (or platform config) generated with unique ports / hostnames.
- [ ] QA ingestion runs completed.
- [ ] Monitoring and logs routed to the correct tenant dashboards.

Once all boxes are checked, the tenant-specific Traceback instance is production-ready. Repeat the process for each additional customer or domain. 🚀

---

## 8. Incident Workflow Trigger (Cloud Function Example)

To generate an incident briefing from a GCP-triggered Cloud Function:

```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "business_area": "claims",
    "query": "BigQuery load failed for dataset claims_dw",
    "incident_payload": {
      "severity": "critical",
      "service": "claims-data-pipeline",
      "timestamp": "2025-05-31T07:12:43Z",
      "error_log": "Job abc123 failed with message: invalid column type"
    },
    "retrieval_plan": {
      "sources": ["confluence", "gitlab", "openmetadata"],
      "limit": 5
    }
  }'
```

The response includes `briefing_summary`, `briefing_markdown`, and `attachments` that can be attached to a ServiceNow ticket. Cloud Functions can forward the payload directly to this endpoint after performing any necessary authentication.


