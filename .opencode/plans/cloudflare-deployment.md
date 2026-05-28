# Cloudflare Deployment Plan for Secondary Brain

## Context

The user wants to deploy the Secondary Brain system to production using:
- **Domain**: `aetherahealthcare.com` (already on Cloudflare)
- **Subdomain**: `kia.aetherahealthcare.com`
- **Hosting**: Local server (no cloud VPS)
- **GPU**: NVIDIA GeForce MX450 with 2GB VRAM
- **CI/CD**: GitHub Actions pipeline

The system is currently running locally with all services verified and working.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Cloudflare Network                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │  Cloudflare Pages│         │ Cloudflare Tunnel│         │
│  │  (Frontend)      │         │  (Secure Conn)   │         │
│  │  Static Vue App  │         │                  │         │
│  └────────┬─────────┘         └────────┬─────────┘         │
│           │                            │                     │
│           │                            │                     │
│           ▼                            ▼                     │
│  kia.aetherahealthcare.com    Tunnel to Local Server        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ (Encrypted Tunnel)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Your Local Server                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Python API   │  │ .NET Gateway │  │   Ollama     │     │
│  │ (FastAPI)    │  │              │  │  (2GB GPU)   │     │
│  │ Port 8000    │  │  Port 5000   │  │ Port 11434   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘     │
│         │                  │                                 │
│         └──────────────────┴──────────────────┐            │
│                                                │            │
│  ┌──────────────┐  ┌──────────────┐  ┌────────▼──────┐    │
│  │    Redis     │  │   Weaviate   │  │   FalkorDB    │    │
│  │  Port 6379   │  │  Port 8081   │  │  Port 6380    │    │
│  └──────────────┘  └──────────────┘  └───────────────┘    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │   Langfuse   │  │  PostgreSQL  │                         │
│  │  Port 3000   │  │  (Langfuse)  │                         │
│  └──────────────┘  └──────────────┘                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Files to Create

### 1. Cloudflare Tunnel Configuration

**File**: `C:\dev\cloudflared\config.yml`

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: C:\Users\YOUR_USER\.cloudflared\YOUR_TUNNEL_ID.json

ingress:
  # Frontend (Cloudflare Pages handles this, but we can proxy if needed)
  - hostname: kia.aetherahealthcare.com
    service: http://localhost:3001
  
  # Backend API
  - hostname: api.kia.aetherahealthcare.com
    service: http://localhost:8000
  
  # .NET Gateway
  - hostname: gateway.kia.aetherahealthcare.com
    service: http://localhost:5000
  
  # Langfuse (optional, for monitoring)
  - hostname: langfuse.kia.aetherahealthcare.com
    service: http://localhost:3000
  
  # Catch-all (required)
  - service: http_status:404
```

### 2. GitHub Actions Workflow

**File**: `C:\dev\.github\workflows\deploy.yml`

```yaml
name: Deploy to Cloudflare

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        run: pip install uv
      
      - name: Install dependencies
        working-directory: ./agents
        run: uv sync
      
      - name: Run linter
        working-directory: ./agents
        run: uv run ruff check .
      
      - name: Run type checker
        working-directory: ./agents
        run: uv run mypy .
      
      - name: Run unit tests
        working-directory: ./agents
        run: uv run pytest tests/unit -v

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci
      
      - name: Build frontend
        working-directory: ./frontend
        run: npm run build
      
      - name: Deploy to Cloudflare Pages
        uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: secondary-brain
          directory: ./frontend/dist
          gitHubToken: ${{ secrets.GITHUB_TOKEN }}

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      
      - name: Build Docker images
        run: |
          docker build -t brain-python-api:latest ./agents
          docker build -t brain-dotnet-gateway:latest ./gateway
      
      - name: Save Docker images
        run: |
          docker save brain-python-api:latest | gzip > python-api.tar.gz
          docker save brain-dotnet-gateway:latest | gzip > dotnet-gateway.tar.gz
      
      - name: Deploy to local server
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.LOCAL_SERVER_IP }}
          username: ${{ secrets.SSH_USERNAME }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          source: "*.tar.gz"
          target: "/tmp/"
      
      - name: Load and restart containers
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.LOCAL_SERVER_IP }}
          username: ${{ secrets.SSH_USERNAME }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            docker load < /tmp/python-api.tar.gz
            docker load < /tmp/dotnet-gateway.tar.gz
            cd /path/to/secondary-brain
            docker-compose -f docker-compose.prod.yml up -d
```

### 3. Deployment Guide

**File**: `C:\dev\CLOUDFLARE_DEPLOYMENT.md`

Complete step-by-step guide covering:
- Prerequisites
- Cloudflare Tunnel setup
- DNS configuration
- Cloudflare Pages deployment
- GitHub secrets configuration
- Backend configuration updates
- Ollama optimization for 2GB VRAM
- Testing and verification
- Troubleshooting

### 4. Updated Backend Configuration

**File**: `C:\dev\agents\api\main.py` (modify existing)

Update CORS to allow Cloudflare domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://kia.aetherahealthcare.com",
        "http://localhost:3001",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5. Updated Environment Variables

**File**: `C:\dev\.env` (modify existing)

```bash
# Production URLs
CORS_ORIGINS=https://kia.aetherahealthcare.com
ENABLE_HTTPS=true

# Ollama (optimized for 2GB VRAM)
OLLAMA_MODEL=qwen3.5:4b
DEFAULT_OSS_MODEL=qwen3.5:4b
```

---

## Implementation Steps

### Phase 1: Prerequisites (15 minutes)

1. **Install Cloudflare Tunnel CLI**
   ```powershell
   winget install cloudflare.cloudflared
   ```

2. **Authenticate with Cloudflare**
   ```powershell
   cloudflared tunnel login
   ```

3. **Push to GitHub**
   ```powershell
   cd C:\dev
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/secondary-brain.git
   git push -u origin main
   ```

### Phase 2: Cloudflare Tunnel Setup (20 minutes)

1. **Create tunnel**
   ```powershell
   cloudflared tunnel create secondary-brain
   ```

2. **Configure tunnel** - Create `cloudflared/config.yml`

3. **Install as Windows service**
   ```powershell
   cloudflared service install
   net start cloudflared
   ```

### Phase 3: DNS Configuration (10 minutes)

1. **Add DNS records in Cloudflare Dashboard**
   - CNAME: `kia` → `YOUR_TUNNEL_ID.cfargotunnel.com`
   - CNAME: `api.kia` → `YOUR_TUNNEL_ID.cfargotunnel.com`
   - CNAME: `gateway.kia` → `YOUR_TUNNEL_ID.cfargotunnel.com`
   - CNAME: `langfuse.kia` → `YOUR_TUNNEL_ID.cfargotunnel.com`

2. **Enable proxy (orange cloud)** for all records

### Phase 4: Cloudflare Pages Deployment (15 minutes)

1. **Go to Cloudflare Dashboard → Pages**

2. **Create project** → Connect to Git

3. **Configure build settings**:
   - Framework preset: Vue
   - Build command: `npm run build`
   - Build output directory: `dist`
   - Root directory: `frontend`

4. **Deploy**

5. **Set custom domain**: `kia.aetherahealthcare.com`

### Phase 5: GitHub Actions Setup (15 minutes)

1. **Create GitHub secrets**:
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
   - `LOCAL_SERVER_IP` (your public IP)
   - `SSH_USERNAME`
   - `SSH_PRIVATE_KEY`

2. **Create API token** at https://dash.cloudflare.com/profile/api-tokens
   - Permissions: Cloudflare Pages Edit, DNS Edit

3. **Push workflow file** to trigger first deployment

### Phase 6: Backend Configuration (10 minutes)

1. **Update CORS** in `agents/api/main.py`

2. **Update environment variables** in `.env`

3. **Restart services**
   ```powershell
   docker-compose -f docker-compose.prod.yml restart
   ```

### Phase 7: Ollama Optimization (10 minutes)

1. **Pull optimized model**
   ```powershell
   ollama pull qwen3.5:4b
   ```

2. **Update docker-compose.prod.yml** with VRAM limits

3. **Restart Ollama**
   ```powershell
   docker-compose -f docker-compose.prod.yml restart ollama
   ```

### Phase 8: Testing & Verification (20 minutes)

1. **Test frontend**: https://kia.aetherahealthcare.com

2. **Test backend API**: https://api.kia.aetherahealthcare.com/health

3. **Test tunnel status**:
   ```powershell
   cloudflared tunnel info secondary-brain
   ```

4. **Run integration tests**:
   ```powershell
   uv run pytest tests/integration -v
   ```

5. **Test LLM generation** via frontend chat interface

---

## GPU Optimization for 2GB VRAM

### Recommended Models

| Model | Size | VRAM Usage | Performance |
|-------|------|------------|-------------|
| `qwen3.5:4b` | 3.4GB | ~1.8GB | Good (Q4_K_M) ✅ |
| `phi3:mini` | 2.3GB | ~1.5GB | Fast ✅ |
| `gemma2:2b` | 1.6GB | ~1.2GB | Very Fast ✅ |
| `llama3.2:3b` | 2.0GB | ~1.4GB | Good ✅ |

### Configuration

```yaml
ollama:
  environment:
    - OLLAMA_HOST=0.0.0.0
    - OLLAMA_NUM_PARALLEL=1  # Reduce parallel requests
    - OLLAMA_MAX_LOADED_MODELS=1  # Only one model at a time
```

---

## Cost Breakdown

| Service | Cost |
|---------|------|
| Cloudflare Pages | Free (unlimited bandwidth) |
| Cloudflare Tunnel | Free |
| Cloudflare DNS | Free |
| Cloudflare SSL/TLS | Free |
| Local Server | Electricity only |
| **Total** | **$0/month** |

---

## Security Considerations

1. **Enable Cloudflare WAF** - Protect against attacks
2. **Use Cloudflare Access** - Add authentication to sensitive endpoints
3. **Rotate API keys regularly** - Update GitHub secrets
4. **Monitor tunnel health** - Set up alerts in Cloudflare
5. **Backup Docker volumes** - Regular backups of Redis, Weaviate, FalkorDB
6. **Use strong passwords** - For Langfuse, PostgreSQL, etc.
7. **Enable rate limiting** - In Cloudflare dashboard

---

## Troubleshooting

### Tunnel not connecting
```powershell
# Check service status
Get-Service cloudflared

# Restart service
Restart-Service cloudflared

# View logs
cloudflared tunnel logs secondary-brain
```

### DNS not resolving
```powershell
# Flush DNS
ipconfig /flushdns

# Check DNS propagation
nslookup kia.aetherahealthcare.com
```

### Ollama out of memory
```powershell
# Use smaller model
ollama pull phi3:mini

# Update .env
OLLAMA_MODEL=phi3:mini
```

### Frontend not loading
- Check Cloudflare Pages deployment logs
- Verify build succeeded in GitHub Actions
- Check browser console for errors

---

## Success Criteria

✅ Frontend accessible at https://kia.aetherahealthcare.com
✅ Backend API accessible at https://api.kia.aetherahealthcare.com/health
✅ Cloudflare Tunnel shows healthy status
✅ GitHub Actions pipeline runs successfully
✅ All integration tests pass
✅ LLM generation works via frontend
✅ SSL/TLS certificates active
✅ DNS records resolve correctly

---

## Next Steps After Deployment

1. **Set up monitoring** - Configure Langfuse with API keys
2. **Set up backups** - Automated backups of Docker volumes
3. **Configure alerts** - Cloudflare notifications for tunnel health
4. **Load testing** - Test system under load
5. **Performance tuning** - Optimize based on usage patterns
6. **Documentation** - Update user documentation with production URLs

---

## Files to Create/Modify

### New Files
1. `C:\dev\cloudflared\config.yml` - Tunnel configuration
2. `C:\dev\.github\workflows\deploy.yml` - GitHub Actions workflow
3. `C:\dev\CLOUDFLARE_DEPLOYMENT.md` - Deployment guide

### Modified Files
1. `C:\dev\agents\api\main.py` - Update CORS
2. `C:\dev\.env` - Update environment variables
3. `C:\dev\docker-compose.prod.yml` - Optimize Ollama for 2GB VRAM

---

## Verification Commands

```powershell
# Check tunnel status
cloudflared tunnel info secondary-brain

# Test frontend
Invoke-WebRequest -Uri "https://kia.aetherahealthcare.com" -UseBasicParsing

# Test backend
Invoke-WebRequest -Uri "https://api.kia.aetherahealthcare.com/health" -UseBasicParsing

# Check DNS
nslookup kia.aetherahealthcare.com

# View tunnel logs
cloudflared tunnel logs secondary-brain

# Check Docker services
docker-compose -f docker-compose.prod.yml ps

# Run integration tests
uv run pytest tests/integration -v
```

---

## Timeline

- **Phase 1-2**: 35 minutes (Prerequisites + Tunnel)
- **Phase 3-4**: 25 minutes (DNS + Pages)
- **Phase 5-6**: 25 minutes (GitHub + Backend)
- **Phase 7-8**: 30 minutes (Optimization + Testing)
- **Total**: ~2 hours

---

## Support Resources

- Cloudflare Docs: https://developers.cloudflare.com/
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- GitHub Actions: https://docs.github.com/en/actions
- Ollama Models: https://ollama.ai/library
