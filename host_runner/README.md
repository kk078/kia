# KIA Host Command Runner

KIA's backend runs inside Docker and **cannot touch your real OS**. This tiny runner is
the bridge that lets KIA execute commands you approve (e.g. install software, run a build)
on the host machine. It is the single most powerful — and most dangerous — component, so
it is opt-in, token-gated, and only ever runs commands you explicitly approve in the chat.

## How the safety model works

```
You type /build install slack
   → KIA proposes the exact commands (no execution)         [/api/v1/exec/plan]
   → You review each command in the chat and click "Run"
   → Backend sends each approved command to THIS runner      [/api/v1/exec/run]
   → Runner executes it on the host, returns output, logs it
```

Nothing runs until you click Run. KIA never invents-and-executes in one step.

## Start it (on the host, NOT in Docker)

1. Pick a long random token (treat it like a password).

   **Windows (PowerShell):**
   ```powershell
   $env:RUNNER_TOKEN = "paste-a-long-random-secret-here"
   python host_runner\runner.py
   ```

   **macOS/Linux:**
   ```bash
   RUNNER_TOKEN="paste-a-long-random-secret-here" python3 host_runner/runner.py
   ```

   It listens on port `8765` (override with `RUNNER_PORT`). On Windows it runs commands
   through PowerShell; on macOS/Linux through bash.

2. Tell KIA's backend about it — add to `C:\dev\.env`:
   ```
   EXEC_ENABLED=true
   HOST_RUNNER_URL=http://host.docker.internal:8765
   HOST_RUNNER_TOKEN=paste-a-long-random-secret-here
   ```
   `host.docker.internal` is how the container reaches your host. Then restart the API:
   ```powershell
   docker compose -f docker-compose.prod.yml up -d python-api
   ```

3. In KIA chat, type `/build <task>` (e.g. `/build install slack`). KIA proposes commands;
   review and approve.

## Security notes (read these)

- The runner binds `0.0.0.0` so Docker can reach it, which means it's reachable from your
  LAN. **The token is the only guard.** Use a long random secret. If you don't run KIA in
  Docker, set `RUNNER_HOST=127.0.0.1` to bind loopback only.
- Consider a firewall rule allowing port 8765 only from localhost and the Docker subnet.
- Every command is appended to `host_runner/host_runner.log` — review it.
- Stop the runner (Ctrl+C) when you're not actively using `/build`. No runner = KIA can't
  execute anything on the host, by design.
- KIA's command *suggestions* come from an LLM and can be wrong. You are the approval gate —
  read each command before clicking Run. Don't approve anything you don't understand.
- The runner does not run as admin unless you start it from an elevated terminal. Installs
  that need admin will fail unless you intentionally launch it elevated.
