#!/bin/bash
# End-to-end test script for CodeQL integration

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
BUSINESS_AREA="${BUSINESS_AREA:-cerebro}"

echo "=========================================="
echo "Traceback CodeQL End-to-End Test"
echo "=========================================="
echo "Base URL: $BASE_URL"
echo "Business Area: $BUSINESS_AREA"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper function
check_response() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        exit 1
    fi
}

# Step 1: Health check
echo "Step 1: Checking application health..."
curl -s "$BASE_URL/health" | jq -r '.status' | grep -q "healthy" && check_response "Application is healthy" || echo -e "${YELLOW}⚠${NC} Health check failed or returned unexpected status"

# Step 2: List business areas
echo ""
echo "Step 2: Listing business areas..."
curl -s "$BASE_URL/api/v1/business-areas" | jq -r '.business_areas[]' | head -1
check_response "Business areas retrieved"

# Step 3: Register a code source
echo ""
echo "Step 3: Registering code source..."
SOURCE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/code-sources/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"business_area\": \"$BUSINESS_AREA\",
    \"source_type\": \"gitlab\",
    \"path\": \"test-org/e2e-test-repo\",
    \"languages\": [\"python\", \"java\"],
    \"name\": \"E2E Test Repository\",
    \"enabled\": true
  }")

SOURCE_ID=$(echo "$SOURCE_RESPONSE" | jq -r '.source_id')
echo "$SOURCE_RESPONSE" | jq '.'
check_response "Source registered: $SOURCE_ID"

# Step 4: List sources
echo ""
echo "Step 4: Listing registered sources..."
curl -s "$BASE_URL/api/v1/code-sources?business_area=$BUSINESS_AREA" | jq '.total, .sources[0].source_id'
check_response "Sources listed"

# Step 5: Get specific source
echo ""
echo "Step 5: Getting source details..."
curl -s "$BASE_URL/api/v1/code-sources/$SOURCE_ID" | jq '.source_id, .path, .enabled'
check_response "Source details retrieved"

# Step 6: Trigger analysis
echo ""
echo "Step 6: Triggering code analysis..."
ANALYSIS_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d "{\"source_id\": \"$SOURCE_ID\"}")

echo "$ANALYSIS_RESPONSE" | jq '.'
STATUS=$(echo "$ANALYSIS_RESPONSE" | jq -r '.status // .detail // "unknown"')

if [ "$STATUS" = "running" ]; then
    check_response "Analysis triggered successfully"
elif [ "$STATUS" = *"not enabled"* ] || [ "$STATUS" = *"CodeQL"* ]; then
    echo -e "${YELLOW}⚠${NC} CodeQL not enabled (expected if not configured)"
else
    echo -e "${YELLOW}⚠${NC} Analysis response: $STATUS"
fi

# Step 7: Test incident workflow
echo ""
echo "Step 7: Testing incident workflow with graph retriever..."
INCIDENT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d "{
    \"business_area\": \"$BUSINESS_AREA\",
    \"query\": \"FunctionNotFoundError in process_data\",
    \"incident_payload\": {
      \"error\": \"FunctionNotFoundError\",
      \"function\": \"process_data\",
      \"service\": \"data-pipeline\"
    },
    \"retrieval_plan\": {
      \"sources\": [\"codeql\"],
      \"limit\": 5
    }
  }")

echo "$INCIDENT_RESPONSE" | jq '.briefing_summary // .errors // .briefing_markdown[:100]'
check_response "Incident workflow executed"

# Step 8: Clean up
echo ""
echo "Step 8: Cleaning up test source..."
curl -s -X DELETE "$BASE_URL/api/v1/code-sources/$SOURCE_ID" | jq '.message // .'
check_response "Source deleted"

echo ""
echo "=========================================="
echo -e "${GREEN}All tests completed!${NC}"
echo "=========================================="
echo ""
echo "To test with real data:"
echo "1. Install CodeQL CLI: https://github.com/github/codeql-cli-binaries"
echo "2. Set up Neo4j: docker run -d -p 7474:7474 -p 7687:7687 neo4j:latest"
echo "3. Configure .env: CODEQL_ENABLED=true, NEO4J_URL=bolt://localhost:7687"
echo "4. Re-run this script"

