# Secondary Brain - Production Deployment Guide

## Overview

This guide covers deploying the Secondary Brain system to production using Docker containers.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │ .NET Gateway │─────▶│ Python API   │                    │
│  │   (port 5000)│      │  (port 8000) │                    │
│  └──────────────┘      └──────┬───────┘                    │
│                                │                             │
│         ┌──────────────────────┼──────────────────────┐    │
│         │                      │                      │    │
│  ┌──────▼──────┐      ┌───────▼──────┐      ┌───────▼──────┐│
│  │    Redis    │      │   Weaviate   │      │   FalkorDB   ││
│  │ (port 6379) │      │ (port 8081)  │      │ (port 6380)  ││
│  └─────────────┘      └──────────────┘      └──────────────┘│
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   Langfuse   │      │ Langfuse DB  │                    │
│  │ (port 3000)  │◀────▶│  (Postgres)  │                    │
│  └──────────────┘      └──────────────┘                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Docker 24.0+ and Docker Compose 2.20+
- 8GB+ RAM available
- 20GB+ disk space
- API keys for LLM providers (Anthropic, OpenAI, etc.)

## Quick Start

### 1. Configure Environment

```powershell
# Copy production template
Copy-Item .env.production .env

# Edit .env with your API keys
notepad .env
```

**Required variables:**
- `ANTHROPIC_API_KEY` - Anthropic Claude API key
- `OPENAI_API_KEY` - OpenAI API key (optional)
- `LANGFUSE_PUBLIC_KEY` - From Langfuse UI after first login
- `LANGFUSE_SECRET_KEY` - From Langfuse UI after first login

### 2. Deploy

```powershell
# Build and start all services
.\scripts\deploy.ps1
```

### 3. Verify

```powershell
# Check service status
docker-compose -f docker-compose.prod.yml ps

# Check health endpoints
curl http://localhost:5000/health  # .NET Gateway
curl http://localhost:8000/health  # Python API
curl http://localhost:3000/api/public/health  # Langfuse
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| .NET Gateway | 5000 | ASP.NET Core unified API |
| Python API | 8000 | FastAPI gateway |
| Redis | 6379 | Working memory + A2A bus |
| Weaviate | 8081 | Vector store (episodic/semantic) |
| FalkorDB | 6380 | Knowledge graph |
| Langfuse | 3000 | LLM observability |

## Management Commands

```powershell
# View logs
.\scripts\logs-prod.ps1                    # All services
.\scripts\logs-prod.ps1 python-api         # Specific service

# Stop services
.\scripts\stop-prod.ps1

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Rebuild after code changes
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

## Monitoring & Observability

### Langfuse (LLM Observability)

Access: http://localhost:3000

1. Create an account on first login
2. Create a project
3. Copy public/secret keys to `.env`:
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`
4. Restart services: `docker-compose -f docker-compose.prod.yml restart`

### Health Checks

All services have health checks configured:
- Interval: 30s
- Timeout: 10s
- Retries: 3

View health status:
```powershell
docker inspect --format='{{.State.Health.Status}}' brain-python-api-prod
docker inspect --format='{{.State.Health.Status}}' brain-dotnet-gateway-prod
```

### Logs

```powershell
# Follow all logs
docker-compose -f docker-compose.prod.yml logs -f

# Follow specific service
docker-compose -f docker-compose.prod.yml logs -f python-api

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100 python-api
```

## API Endpoints

### .NET Gateway (port 5000)

- `GET /health` - Health check
- `GET /swagger` - API documentation (dev only)
- All Python API endpoints proxied

### Python API (port 8000)

- `GET /health` - Health check
- `GET /api/v1/status` - System status
- `POST /api/v1/memory/episodes` - Store episode
- `GET /api/v1/memory/episodes` - Retrieve episodes
- `POST /api/v1/memory/facts` - Store fact
- `GET /api/v1/memory/facts` - Query facts
- `POST /api/v1/orchestrator/run` - Run orchestrator
- `POST /api/v1/llm/generate` - Generate text
- `GET /api/v1/llm/route` - Get model route
- `POST /api/v1/knowledge/index` - Index document
- `GET /api/v1/knowledge/retrieve` - Retrieve context
- `POST /api/v1/knowledge/rag` - RAG query

## Security Considerations

### Production Checklist

- [ ] Change all default passwords in `.env`
- [ ] Set `LANGFUSE_DB_PASSWORD` to a strong password
- [ ] Set `LANGFUSE_SECRET` and `LANGFUSE_SALT` to random values
- [ ] Configure `CORS_ORIGINS` to your domain
- [ ] Enable HTTPS (reverse proxy or load balancer)
- [ ] Restrict network access to internal services
- [ ] Set up firewall rules
- [ ] Enable rate limiting
- [ ] Configure log rotation
- [ ] Set up backups for volumes

### Network Security

The production compose uses an internal Docker network. Only these ports are exposed:
- 5000 (.NET Gateway)
- 8000 (Python API)
- 3000 (Langfuse UI)

Infrastructure services (Redis, Weaviate, FalkorDB) are NOT exposed externally.

## Scaling

### Horizontal Scaling

For production workloads, consider:
1. **Load Balancer**: Add nginx/HAProxy in front of services
2. **Redis Cluster**: For high availability
3. **Weaviate Cluster**: Multi-node setup
4. **PostgreSQL**: Managed database service

### Resource Limits

Add resource limits to `docker-compose.prod.yml`:

```yaml
services:
  python-api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Troubleshooting

### Services won't start

```powershell
# Check logs
docker-compose -f docker-compose.prod.yml logs

# Check if ports are in use
netstat -ano | findstr "5000 8000 3000"

# Restart services
docker-compose -f docker-compose.prod.yml restart
```

### Health checks failing

```powershell
# Check health status
docker inspect brain-python-api-prod | Select-String "Health"

# View health check logs
docker inspect --format='{{json .State.Health}}' brain-python-api-prod
```

### Database connection issues

```powershell
# Check if database is ready
docker-compose -f docker-compose.prod.yml logs langfuse-db

# Restart database
docker-compose -f docker-compose.prod.yml restart langfuse-db
```

## Backup & Recovery

### Backup Volumes

```powershell
# Backup Redis
docker run --rm -v brain_redis-data:/data -v ${PWD}:/backup alpine tar czf /backup/redis-backup.tar.gz /data

# Backup Weaviate
docker run --rm -v brain_weaviate-data:/data -v ${PWD}:/backup alpine tar czf /backup/weaviate-backup.tar.gz /data

# Backup PostgreSQL
docker exec brain-langfuse-db-prod pg_dump -U langfuse langfuse > langfuse-backup.sql
```

### Restore Volumes

```powershell
# Restore Redis
docker run --rm -v brain_redis-data:/data -v ${PWD}:/backup alpine tar xzf /backup/redis-backup.tar.gz -C /

# Restore Weaviate
docker run --rm -v brain_weaviate-data:/data -v ${PWD}:/backup alpine tar xzf /backup/weaviate-backup.tar.gz -C /

# Restore PostgreSQL
docker exec -i brain-langfuse-db-prod psql -U langfuse langfuse < langfuse-backup.sql
```

## Updates

### Update Application Code

```powershell
# Pull latest code
git pull

# Rebuild images
docker-compose -f docker-compose.prod.yml build

# Restart services
docker-compose -f docker-compose.prod.yml up -d
```

### Update Infrastructure

```powershell
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Restart services
docker-compose -f docker-compose.prod.yml up -d
```

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/secondary-brain/issues
- Documentation: See `/docs` directory
