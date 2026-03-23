---
name: deploy
description: >-
  This skill should be used when the user asks to "deploy", "update docker",
  "restart container", "pull latest image", "release new version",
  "check deployment status", "update production", "docker compose up",
  "rebuild container", or mentions Docker deployment workflows.
---

# Docker Deployment

Manage Docker-based deployment of OMRON Garmin Bridge — pull images, restart
containers, verify health, and handle production/dev environments.

## Deployment Architecture

Two Docker Compose configurations:

| File | Purpose | Image Source |
|------|---------|-------------|
| `docker/docker-compose.yaml` | Production | `ghcr.io/jacekzubielik/omron-garmin-bridge:latest` |
| `docker/docker-compose.dev.yaml` | Development | `ghcr.io/jacekzubielik/omron-garmin-bridge:dev` |

Both use `network_mode: host` (required for BLE) and `privileged: true`.

## Production Update

To update to the latest release:

```bash
docker compose -f docker/docker-compose.yaml pull
docker compose -f docker/docker-compose.yaml up -d
```

**Critical:** Always `pull` first — without it Docker uses cached `:latest` from local store.

## Development Deployment

```bash
docker compose -f docker/docker-compose.dev.yaml pull
docker compose -f docker/docker-compose.dev.yaml up -d
```

## Health Verification

After deployment, verify the container is healthy:

```bash
# Check container status
docker ps --filter name=omron-garmin-bridge

# Check health endpoint (Streamlit)
curl -sf http://localhost:8501/_stcore/health

# Check logs for startup errors
docker logs omron-garmin-bridge --tail 50
```

Healthcheck is built into compose: `curl -f http://localhost:8501/_stcore/health`
every 30s with 40s start period.

## Pre-deployment Checklist

Before deploying, verify:

1. **Config**: `config/config.yaml` exists and is valid
2. **Tokens**: `data/tokens/<email>/` contains OAuth files
3. **Database**: `data/omron.db` is accessible (will be created if missing)
4. **Port**: 8501 is available (or stop existing container first)
5. **Bluetooth**: D-Bus and BlueZ mounts are available

## Volume Mounts

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `config/config.yaml` | `/app/config/config.yaml:ro` | Configuration |
| `data/` | `/app/data` | SQLite DB + OAuth tokens |
| `logs/` | `/app/logs` | Application logs |
| `/var/run/dbus` | `/var/run/dbus` | D-Bus for BlueZ |
| `/var/lib/bluetooth` | `/var/lib/bluetooth:ro` | BLE pairing state |

## Release Pipeline

Release is automated via GitHub Actions (`release.yml`):

1. Push to `main` triggers semantic-release
2. If version bump detected: tag + GitHub release + CHANGELOG
3. Docker image built and pushed to `ghcr.io` with semver tags

## Scripts

- **`scripts/deploy.sh`** — Pull and restart production container with health verification
