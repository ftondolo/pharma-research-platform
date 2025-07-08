#!/bin/bash

# Pharmaceutical Research Platform - Startup Script

set -e

echo "Starting Pharmaceutical Research Platform..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.template .env
    echo "Please edit .env file with your API keys before running again."
    exit 1
fi

# Source environment variables
source .env

# Check required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY is required. Please set it in .env file."
    exit 1
fi

echo "Environment variables loaded..."

# Function to check if service is running
check_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:$port/health > /dev/null 2>&1; then
            echo "$service is ready!"
            return 0
        fi
        echo "Waiting for $service to be ready... ($((attempt + 1))/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    echo "Error: $service failed to start within expected time"
    return 1
}

# Start services with Docker Compose
echo "Starting database and Redis..."
docker-compose up -d postgres redis

echo "Waiting for database to be ready..."
sleep 10

echo "Starting backend services..."
docker-compose up -d backend

echo "Waiting for backend to be ready..."
sleep 15

echo "Starting frontend..."
docker-compose up -d frontend

echo "Waiting for services to be ready..."
sleep 10

# Check if services are running
echo "Checking service health..."

# Check backend
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ Backend is running at http://localhost:8000"
else
    echo "✗ Backend failed to start"
    echo "Check logs with: docker-compose logs backend"
    exit 1
fi

# Check frontend
if curl -s http://localhost:3000 > /dev/null; then
    echo "✓ Frontend is running at http://localhost:3000"
else
    echo "✗ Frontend failed to start"
    echo "Check logs with: docker-compose logs frontend"
    exit 1
fi

echo ""
echo "🚀 Pharmaceutical Research Platform is ready!"
echo ""
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""
echo "To stop services: docker-compose down"
echo "To view logs: docker-compose logs -f"
echo ""
echo "Happy researching! 🔬"
