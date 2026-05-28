# Deploying Secondary Brain to Cloudflare

Target: **https://kia.aetherahealthcare.com**

## Architecture

```
Browser ──► kia.aetherahealthcare.com
              │
              ├── /            → Cloudflare Pages (Vue frontend)   [Cloudflare Access]
              └── /api/* /health → Cloudflare Worker (kia-api-proxy) [Cloudflare Access]
                                      │  injects Access service token
                                      ▼
                            origin.aetherahealthcare.com  (Cloudflare Tunnel)
                                      │  [Access: service-token policy]
                                      ▼
                            Local server  →  FastAPI :8000
                                              .NET gateway :5000
                                              Redis / Weaviate / FalkorDB
                                              Langfuse / Postgres / Ollama (GPU)
```

**Why this shape:** Cloudflare Workers/Pages can't run the Python/.NET agent stack or
the stateful databases + Ollama. So Pages serves the static frontend, a Worker is the
edge API gateway (auth headers, CORS, rate-limit), and the real backend runs as the
existing Docker stack on your machine, reached securely over a Cloudflare Tunnel.

Everything below is **free** (Pages, Workers free tier, Tunnel, DNS, Access for up to 50 users).

---

## Files in this repo

| Path | Purpose |
|------|---------|
| `worker/wrangler.toml` | Worker config + route `kia.aetherahealthcare.com/api/*` |
| `worker/src/index.js` | The proxy: forwards to the tunnel origin, injects Access service token |
| `cloudflared/config.example.yml` | Tunnel ingress (copy to `config.yml`) |
| `frontend/public/_redirects` | SPA history-mode fallback for Pages |
| `frontend/public/_headers` | Security headers for Pages |
| `.github/workflows/deploy.yml` | CI: test → deploy Pages → deploy Worker |
| `agents/api/main.py` | CORS allow-list updated for the domain |

---

## One-time setup

### 0. Prerequisites
```powershell
winget install cloudflare.cloudflared
npm install -g wrangler
```
> **Multiple Cloudflare accounts?** Do NOT use `wrangler login` (it stores one global
> OAuth session and can point at the wrong account). Instead authenticate per-command
> with an account-scoped API token — see "Using a separate Cloudflare account" below.
> Set the token + account id in your shell, then confirm:
> ```powershell
> $env:CLOUDFLARE_API_TOKEN="<token for the kia account>"
> $env:CLOUDFLARE_ACCOUNT_ID="<kia account id>"
> wrangler whoami        # verify it shows the intended account
> ```

### 1. Create the Tunnel (local backend)
```powershell
cd C:\dev
cloudflared tunnel create secondary-brain
# note the Tunnel ID it prints

copy cloudflared\config.example.yml cloudflared\config.yml
# edit config.yml: paste the Tunnel ID + credentials path

# Route the origin hostname to this tunnel:
cloudflared tunnel route dns secondary-brain origin.aetherahealthcare.com

# Start the local backend first:
docker compose -f docker-compose.prod.yml up -d

# Run the tunnel (install as a service so it stays up):
cloudflared service install
net start cloudflared
```

### 2. Lock the origin behind an Access service token
In the Cloudflare dashboard → **Zero Trust → Access**:
1. **Service Auth → Service Tokens → Create** → name it `kia-worker`. Copy the
   **Client ID** and **Client Secret** (shown once).
2. **Applications → Add → Self-hosted**, domain `origin.aetherahealthcare.com`.
   Add a policy: **Action = Service Auth**, include the `kia-worker` service token.
   This means only requests carrying that token (i.e. the Worker) reach the backend.

### 3. Deploy the Worker
```powershell
cd C:\dev\worker
npm install
wrangler secret put CF_ACCESS_CLIENT_ID       # paste service-token Client ID
wrangler secret put CF_ACCESS_CLIENT_SECRET    # paste service-token Client Secret
wrangler deploy
```
The route in `wrangler.toml` binds the Worker to `kia.aetherahealthcare.com/api/*`
and `/health`.

### 4. Deploy the frontend to Pages
Option A — dashboard (Git integration):
- **Pages → Create → Connect to Git → kk078/kia**
- Build command: `npm run build` · Output dir: `dist` · Root dir: `frontend`
- After first build, **Custom domains → add `kia.aetherahealthcare.com`**

Option B — CLI:
```powershell
cd C:\dev\frontend
npm ci && npm run build
wrangler pages project create kia --production-branch main
wrangler pages deploy dist --project-name=kia
```

### 5. Protect the app with Cloudflare Access (interactive login)
Zero Trust → **Access → Applications → Add → Self-hosted**:
- Domain: `kia.aetherahealthcare.com` (covers both Pages and the Worker route)
- Policy: **Allow**, include rule **Emails → kirkmar078@gmail.com** (add others as needed)
- Choose login method (One-time PIN works with no IdP setup)

### 6. GitHub Actions (auto-deploy on push)
Repo → **Settings → Secrets and variables → Actions**, add:
- `CLOUDFLARE_API_TOKEN` — create at dash → API Tokens with **Pages:Edit**,
  **Workers Scripts:Edit**, **Account:Read**, **Zone:Read** (Workers Routes:Edit)
- `CLOUDFLARE_ACCOUNT_ID` — from the dashboard sidebar

On every push to `master`/`main`, CI runs tests, deploys Pages, and deploys the Worker.
(The backend is **not** deployed by CI — it lives on your local server via the tunnel.)

---

## Using a separate Cloudflare account (avoiding conflicts)

You run other projects under a different Cloudflare account, so isolate this one:

1. **Pin the account in code.** `worker/wrangler.toml` has `account_id = "<kia account id>"`.
   Fill it in. Wrangler will refuse to deploy anywhere else.
2. **Use an account-scoped API token, not `wrangler login`.** Create the token while
   logged into the *kia* account (API Tokens page), then export it as
   `CLOUDFLARE_API_TOKEN` for wrangler/cloudflared commands. The token is bound to that
   one account, so your global login state is irrelevant. `wrangler whoami` confirms.
3. **GitHub is already isolated.** Actions secrets are per-repo — `kk078/kia` holds the
   *kia* account's `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`; your other repos keep
   their own. No cross-talk.
4. **Tunnel: prefer a token-based (remotely-managed) tunnel** so you don't disturb the
   `cert.pem` your other account uses:
   - Zero Trust → **Networks → Tunnels → Create a tunnel** (in the *kia* account).
   - Copy the tunnel **token**, then run it without any global login:
     ```powershell
     cloudflared service install <TUNNEL_TOKEN>     # installs + starts as a service
     ```
   - Add the public hostname `origin.aetherahealthcare.com` → `http://localhost:8000`
     in that tunnel's **Public Hostnames** tab (replaces the local `config.yml` ingress).
   - If you prefer the CLI/`config.yml` method instead, keep accounts apart with a
     dedicated cert + config dir:
     ```powershell
     cloudflared tunnel --origincert C:\dev\cloudflared\kia-cert.pem login
     cloudflared tunnel --config C:\dev\cloudflared\config.yml run secondary-brain
     ```

## Verify
```powershell
nslookup kia.aetherahealthcare.com
cloudflared tunnel info secondary-brain
# In a browser (you'll hit the Access login first):
#   https://kia.aetherahealthcare.com           -> the app
#   https://kia.aetherahealthcare.com/health     -> {"status":"healthy",...}
```

---

## Notes & gotchas
- **The local machine must be running** (backend + cloudflared) whenever the site is used.
- **Ollama on 2GB VRAM:** prefer a small model — `gemma2:2b`, `llama3.2:3b`, or `phi3:mini`.
  Set `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_MAX_LOADED_MODELS=1`.
- **Rate limiting:** either enable the KV block in `worker/wrangler.toml`
  (`wrangler kv namespace create RATE_LIMIT`) or add a Cloudflare WAF Rate-Limiting rule.
- **CORS:** the Worker proxies same-origin so the browser sees no cross-origin call;
  the backend allow-list in `agents/api/main.py` is a belt-and-suspenders measure.
- **`.dev.vars`** in `worker/` can hold the two Access secrets for `wrangler dev` (gitignored).
