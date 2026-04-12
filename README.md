# DevHelm MCP Server

[Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for [DevHelm](https://devhelm.io) — gives AI coding assistants (Cursor, Claude Desktop, Windsurf, etc.) access to your uptime monitors, incidents, alerting, and more.

## Quick Start

### Hosted (recommended)

Use the hosted server at `mcp.devhelm.io`. Two connection modes:

**Bearer auth:**
```
URL: https://mcp.devhelm.io/mcp
Authorization: Bearer <your-api-token>
```

**API key in URL** (for clients that only accept a URL):
```
URL: https://mcp.devhelm.io/<your-api-token>/mcp
```

### Local (stdio)

```bash
pip install devhelm-mcp-server
export DEVHELM_API_TOKEN=your-token
devhelm-mcp
```

### Cursor / Claude Desktop

Add to your MCP config:

```json
{
  "mcpServers": {
    "devhelm": {
      "url": "https://mcp.devhelm.io/<your-api-token>/mcp"
    }
  }
}
```

## Available Tools

| Category | Tools |
|----------|-------|
| **Monitors** | list, get, create, update, delete, pause, resume, test, results, versions |
| **Incidents** | list, get, create, resolve, delete |
| **Alert Channels** | list, get, create, update, delete, test |
| **Notification Policies** | list, get, create, update, delete, test |
| **Environments** | list, get, create, update, delete |
| **Secrets** | list, create, update, delete |
| **Tags** | list, get, create, update, delete |
| **Resource Groups** | list, get, create, update, delete, add member, remove member |
| **Webhooks** | list, get, create, update, delete, test |
| **API Keys** | list, create, revoke, delete |
| **Dependencies** | list, get, track, delete |
| **Deploy Lock** | acquire, current, release, force-release |
| **Status** | overview |

## Development

```bash
uv sync
make dev          # Start with MCP Inspector (stdio)
make serve        # Start HTTP server on :8000
make test         # Run unit tests
make lint         # Check formatting
make typecheck    # Run mypy
```

## License

MIT
