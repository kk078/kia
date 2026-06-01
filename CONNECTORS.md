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
- **ConnectorAgent** (`brain_connectors/agent.py`) runs the tool-calling loop. The
  *tool-planning* step uses `CONNECTOR_PLANNER_MODEL` if set (recommended: a strong
  cloud model, since small local models pick tools unreliably), and falls back to the
  local model otherwise.

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

## Adding any connector

Any MCP server works — just add it to `data/connectors.json`:
```json
{ "mcpServers": { "notion": {
    "command": "npx", "args": ["-y", "@modelcontextprotocol/server-notion"],
    "env": {"NOTION_API_KEY": "secret_xxx"} } } }
```
Browse servers at modelcontextprotocol.io / the MCP servers registry. Filesystem,
GitHub, Brave search, and Slack are pre-listed in `connectors.example.json`.

> Note: `@modelcontextprotocol/server-github` is marked deprecated on npm but still
> works. For long-term use, GitHub's official MCP server (github.com/github/github-mcp-server)
> is the maintained option — add it as a command entry pointing at its binary/Docker image.

## Security note

Connector tool output is untrusted input — KIA's guard layer (`brain_core/security`)
sanitizes ingested content. Keep connector tokens in `data/connectors.json` (gitignored),
never commit them.
