#!/usr/bin/env bash
# Deploy OMRON Garmin Bridge production container
# Usage: ./deploy.sh [prod|dev]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV="${1:-prod}"

case "$ENV" in
  prod)
    COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.yaml"
    ;;
  dev)
    COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.dev.yaml"
    ;;
  *)
    echo "Usage: $0 [prod|dev]"
    exit 1
    ;;
esac

echo "=== Deploying $ENV ==="
echo "Compose file: $COMPOSE_FILE"

# Pull latest image
echo "Pulling latest image..."
docker compose -f "$COMPOSE_FILE" pull

# Restart container
echo "Restarting container..."
docker compose -f "$COMPOSE_FILE" up -d

# Wait for health
echo "Waiting for health check..."
for i in $(seq 1 12); do
  if curl -sf http://localhost:8501/_stcore/health > /dev/null 2>&1; then
    echo "Container healthy after ${i}0 seconds"
    docker ps --filter name=omron-garmin-bridge --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
    exit 0
  fi
  sleep 10
done

echo "ERROR: Container not healthy after 120 seconds"
docker logs omron-garmin-bridge --tail 20
exit 1
