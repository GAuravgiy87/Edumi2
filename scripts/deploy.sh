#!/bin/bash

set -e

PROJECT_DIR="/mnt/c/Users/hp123/Documents/classwork/Edumi2"

echo ""
echo "========================================"
echo "      EDUMI2 DEPLOYMENT SCRIPT"
echo "========================================"
echo ""

# Verify project directory exists

if [ ! -d "$PROJECT_DIR" ]; then
echo "ERROR: Project directory not found:"
echo "$PROJECT_DIR"
exit 1
fi

cd "$PROJECT_DIR"

echo "Current Directory:"
pwd

echo ""
echo "Stopping existing containers..."
docker compose down --remove-orphans || true

echo ""
echo "Removing stopped containers..."
docker container prune -f || true

echo ""
echo "Removing unused networks..."
docker network prune -f || true

echo ""
echo "Building Docker images..."
docker compose build --no-cache

echo ""
echo "Starting containers..."
docker compose up -d

echo ""
echo "Waiting for services to start..."
sleep 15

echo ""
echo "========================================"
echo "RUNNING CONTAINERS"
echo "========================================"
docker ps

echo ""
echo "========================================"
echo "DOCKER COMPOSE STATUS"
echo "========================================"
docker compose ps

echo ""
echo "========================================"
echo "LAST 50 LOG LINES"
echo "========================================"
docker compose logs --tail=50

echo ""
echo "========================================"
echo "DEPLOYMENT COMPLETED"
echo "========================================"
echo ""
