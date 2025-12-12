#!/bin/bash
# Traceback Startup Script
# This script starts all required infrastructure services and the Traceback API

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Traceback Startup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if a service is running
check_service() {
    local service_name=$1
    local port=$2
    local health_endpoint=$3
    
    if docker ps | grep -q "$service_name"; then
        if [ -n "$health_endpoint" ]; then
            if curl -sf "$health_endpoint" > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC} $service_name is running and healthy"
                return 0
            else
                echo -e "${YELLOW}⚠${NC} $service_name is running but not healthy"
                return 1
            fi
        else
            echo -e "${GREEN}✓${NC} $service_name is running"
            return 0
        fi
    else
        echo -e "${RED}✗${NC} $service_name is not running"
        return 1
    fi
}

# Step 1: Check prerequisites
echo -e "${BLUE}[1/6] Checking prerequisites...${NC}"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}✗${NC} .env file not found!"
    echo "Please create a .env file with required configuration."
    exit 1
fi
echo -e "${GREEN}✓${NC} .env file found"

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Docker is not running!"
    echo "Please start Docker Desktop and try again."
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker is running"

# Check if docker-compose is available
if ! command -v docker-compose > /dev/null 2>&1 && ! docker compose version > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} docker-compose not found!"
    exit 1
fi
echo -e "${GREEN}✓${NC} docker-compose available"

# Check if Python is available
if ! command -v python3 > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Python 3 not found!"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 3 available"

echo ""

# Step 2: Stop old containers (if any)
echo -e "${BLUE}[2/6] Cleaning up old containers...${NC}"
docker-compose down 2>/dev/null || true
echo -e "${GREEN}✓${NC} Cleanup complete"
echo ""

# Step 3: Start Qdrant
echo -e "${BLUE}[3/6] Starting Qdrant (Vector Database)...${NC}"
docker-compose up -d qdrant

# Wait for Qdrant to be healthy
echo "Waiting for Qdrant to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Qdrant is healthy"
        break
    fi
    attempt=$((attempt + 1))
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗${NC} Qdrant failed to start. Check logs: docker logs traceback-qdrant"
    exit 1
fi
echo ""

# Step 4: Start Redis
echo -e "${BLUE}[4/6] Starting Redis (Cache)...${NC}"
docker-compose up -d redis

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
max_attempts=15
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec traceback-redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Redis is healthy"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗${NC} Redis failed to start. Check logs: docker logs traceback-redis"
    exit 1
fi
echo ""

# Step 5: Check if Neo4j is needed
echo -e "${BLUE}[5/6] Checking CodeQL/Neo4j configuration...${NC}"
if grep -q "CODEQL_ENABLED=true" .env 2>/dev/null; then
    echo "CodeQL is enabled, starting Neo4j..."
    docker-compose up -d neo4j
    
    # Wait for Neo4j to be ready
    echo "Waiting for Neo4j to be ready..."
    max_attempts=30
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:7474 > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Neo4j is healthy"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo -e "${YELLOW}⚠${NC} Neo4j may still be starting. Check logs: docker logs traceback-neo4j"
    fi
else
    echo "CodeQL is disabled, skipping Neo4j"
fi
echo ""

# Step 6: Verify all services
echo -e "${BLUE}[6/6] Verifying all services...${NC}"
echo ""

all_healthy=true

# Check Qdrant
if ! check_service "traceback-qdrant" 6333 "http://localhost:6333/healthz"; then
    all_healthy=false
fi

# Check Redis
if ! docker exec traceback-redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} Redis is not responding"
    all_healthy=false
else
    echo -e "${GREEN}✓${NC} Redis is running and healthy"
fi

# Check Neo4j (if enabled)
if grep -q "CODEQL_ENABLED=true" .env 2>/dev/null; then
    if ! check_service "traceback-neo4j" 7687 "http://localhost:7474"; then
        all_healthy=false
    fi
fi

echo ""

# Final status
if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  All infrastructure services are ready!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo ""
    echo "1. Start the Traceback API:"
    echo -e "   ${YELLOW}uvicorn app.main:app --reload --port 8000${NC}"
    echo ""
    echo "   OR using Docker:"
    echo -e "   ${YELLOW}docker-compose up -d api${NC}"
    echo ""
    echo "2. Verify API is running:"
    echo -e "   ${YELLOW}curl http://localhost:8000/health${NC}"
    echo ""
    echo "3. Access API documentation:"
    echo -e "   ${YELLOW}http://localhost:8000/docs${NC}"
    echo ""
    echo "4. View service logs:"
    echo -e "   ${YELLOW}docker-compose logs -f${NC}"
    echo ""
else
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  Some services may not be healthy${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo "Check logs:"
    echo "  docker-compose logs qdrant"
    echo "  docker-compose logs redis"
    if grep -q "CODEQL_ENABLED=true" .env 2>/dev/null; then
        echo "  docker-compose logs neo4j"
    fi
    exit 1
fi
