#!/bin/bash
# Traceback Stop Script
# Stops all Traceback services gracefully

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Stopping Traceback Services${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Stop all services
docker-compose down

echo ""
echo -e "${GREEN}✓${NC} All services stopped"
echo ""
echo "To start again, run: ./start.sh"

