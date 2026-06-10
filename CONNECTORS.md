# KIA Connectors & Plugins (MCP)

KIA connects to **MCP servers** — the same open standard Claude uses for connectors
(Slack, GitHub, Gmail, Notion, filesystem, web search, ...). KIA acts as an MCP
*client*: it launches configured servers, discovers their tools, and calls them on
your behalf during a chat.

## How it works

```
/api/v1/connectors/query  ->  ConnectorAgent (hybrid tool-calling loop)
                                   |  planner model decides which tool + args
                                   v
                              MCPConnectorManager  ->  MCP servers (stdio)
                                                        filesystem / github / web / slack
```

- **MCPConnectorManager** (`brain_connectors/client.py`) launches each server from
  `connectors.json`, discovers tools, executes calls.
- **ConnectorPool** (`brain_connectors/pool.py`) keeps ONE connected manager alive
  per process (servers are not relaunched on every request — warm calls are ~30x
  faster) and reconnects automatically when `connectors.json` changes.
- **ConnectorAgent** (`brain_connectors/agent.py`) runs the tool-calling loop. The
  *tool-planning* step uses `CONNECTOR_PLANNER_MODEL` if set (recommended: a strong
  cloud model, since small local models pick tools unreliably), and falls back to the
  local model otherwise.

## Security model: ambient vs explicit

- **Plain chat** (the live-retrieval phase) only ever sees **read-only** connector
  tools — reads, lists, searches, fetches (`is_readonly_tool` in
  `brain_connectors/client.py`, enforced both at tool-offering and at dispatch).
  Chat can look things up; it cannot write files, push to repos, or mutate memory.
- **`/api/v1/connectors/query`** (explicit invocation) gets the FULL toolset,
  including writes within the filesystem server's allowed directories.
- **`/agent`** remains the surface for system-level changes, with approval gates.

## Honest limitation

Connecting is easy; **using tools well depends on the model**. A 1.5–3B local model
emits tool calls but often picks the wrong tool or bad arguments. The hybrid design
(`CONNECTOR_PLANNER_MODEL=<cloud model>`) routes only the tool-deciding step to a
strong model so connector reliability approaches Claude's, while generation stays local.

## Setup

1. **Configure servers** — copy the example and fill in secrets:
   ```
   cp connectors.example.json data/connectors.json
   # edit data/connectors.json: GitHub token, Brave/Slack keys, etc.
   ```
   The shape is identical to Claude's `mcpServers` config, so any MCP server works.

2. **Enable + pick a planner** in `.env`:
   ```
   CONNECTORS_ENABLED=true
   CONNECTOR_PLANNER_MODEL=ollama_chat/gpt-oss:120b   # cloud planner (recommended)
   ```
   For the cloud planner you also point Ollama at the cloud endpoint / use your key.

3. **Rebuild** (Dockerfile now includes Node for npx-launched servers):
   ```
   docker compose -f docker-compose.prod.yml up -d --build python-api
   ```

4. **Verify + use**:
   ```
   curl.exe -s http://localhost:8000/api/v1/connectors/list
   curl.exe -s -X POST "http://localhost:8000/api/v1/connectors/query?prompt=List%20open%20issues%20in%20my%20kia%20repo"
   ```

## Bundled servers

`connectors.example.json` ships with eight servers ready to enable (delete any you
don't use so KIA doesn't try to launch it):

| Server | Package | What it adds | Secret needed |
|--------|---------|--------------|---------------|
| `filesystem` | `@modelcontextprotocol/server-filesystem` | Read/write files under `/app/data` | — |
| `github` | `@modelcontextprotocol/server-github` | Repos, issues, PRs, code search | `GITHUB_PERSONAL_ACCESS_TOKEN` |
| `web-search` | `@modelcontextprotocol/server-brave-search` | Web search (SERP) | `BRAVE_API_KEY` |
| `fetch` | `mcp-server-fetch` (uvx) | Fetch & read any web page as markdown | — |
| `postgres` | `@modelcontextprotocol/server-postgres` | Read-only SQL queries | connection string |
| `memory` | `@modelcontextprotocol/server-memory` | Persistent knowledge-graph memory | — |
| `notion` | `@notionhq/notion-mcp-server` | Notion pages/databases | `NOTION_TOKEN` |
| `slack` | `@modelcontextprotocol/server-slack` | Channels, messages | `SLACK_BOT_TOKEN`, `SLACK_TEAM_ID` |

Setup notes for the ones that need it:

- **fetch** — Python server, launched with `uvx` (already in the image). Best paired
  with `web-search`: search for a URL, then fetch and read the page. No key.
- **postgres** — replace the connection string with your DB; use a **read-only** role.
  For SQLite instead, swap to `@modelcontextprotocol/server-sqlite` pointed at
  `/app/data/kia.db`.
- **memory** — a knowledge graph the model can write entities/relations into; persists
  to `MEMORY_FILE_PATH` (`/app/data/mcp_memory.json`) so it survives restarts. This is
  KIA's *connector-side* scratch memory, separate from the Weaviate/FalkorDB stores.
- **notion** — create an internal integration at notion.so/my-integrations, **share the
  pages/databases** with it, then paste the `ntn_…` secret into `NOTION_TOKEN`.
- **Google Drive** — not a one-line `npx`; it needs an OAuth flow. See `_note_gdrive`
  in `connectors.example.json` for the build + credentials steps.

## Adding any other connector

Any MCP server works — just add it to `data/connectors.json` under `mcpServers`:
```json
{ "mcpServers": { "my-server": {
    "command": "npx", "args": ["-y", "@scope/server-name"],
    "env": {"API_KEY": "secret_xxx"} } } }
```
Browse servers at modelcontextprotocol.io / the MCP servers registry.

> Note: `@modelcontextprotocol/server-github` is marked deprecated on npm but still
> works. For long-term use, GitHub's official MCP server (github.com/github/github-mcp-server)
> is the maintained option — add it as a command entry pointing at its binary/Docker image.

## Security note

Connector tool output is untrusted input — KIA's guard layer (`brain_core/security`)
sanitizes ingested content. Keep connector tokens in `data/connectors.json` (gitignored),
never commit them.
