#!/bin/bash

echo "🚀 Starting Traceback System..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env and add your GOOGLE_API_KEY"
    echo "   Then run this script again."
    exit 1
fi

# Check if GOOGLE_API_KEY is set
if grep -q "GOOGLE_API_KEY=your_google_api_key_here" .env; then
    echo "⚠️  Please update GOOGLE_API_KEY in .env file"
    echo "   Get your key from: https://aistudio.google.com/app/apikey"
    exit 1
fi

echo "📦 Starting Docker services..."
echo "   This will take a few minutes on first run (building images)..."
echo ""

# Start services
docker-compose up --build

# Note: Use Ctrl+C to stop
