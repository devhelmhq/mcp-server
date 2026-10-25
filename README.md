# DevHelm MCP Server

<!-- mcp-name: io.github.devhelmhq/mcp-server -->

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
devhelm-mcp-server
```

Or with `uvx` (no install required):

```bash
export DEVHELM_API_TOKEN=your-token
uvx devhelm-mcp-server
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
| **Monitors** | list, get, create, update (inline `code` for BROWSER / MULTI_STEP_API), delete (confirmation), restore, trash, pause, resume, mute, unmute, quarantine, release quarantine, drift, versions, history (`list_monitor_results` is a deprecated alias until 2027-01-31) |
| **Code checks** | test, probe, test ad hoc, run now, trigger; revisions list, get, files, create draft, test, diff, discard; publish and rollback (confirmation), rollback preview |
| **Runs** | get (run envelope, `wait_s` ≤ 25), list, steps, console, network, artifacts (screenshots as images, traces/HARs as signed URLs), trace summary, diff, cancel |
| **Account** | runtimes list/get, usage, entitlements |
| **Incidents** | list, get, create, update, acknowledge, add update, resolve, runs, events, related, trigger; prompt `investigate_incident` |
| **Alert Channels** | list, get, create, update, delete, test |
| **Notification Policies** | list, get, create, update, delete, test |
| **Environments** | list, get, create, update, delete |
| **Secrets** | list, set value, create, update (values via elicitation or a dashboard link, never in chat), delete |
| **Tags** | list, get, create, update, delete |
| **Resource Groups** | list, get, create, update, delete, add member, remove member |
| **Webhooks** | list, get, create, update, delete, test |
| **API Keys** | list, create, revoke, delete |
| **Dependencies** | list, get, track, delete |
| **Deploy Lock** | acquire, current, release, force-release |
| **Status** | overview |
| **Status Pages** | pages, components, groups, incidents, maintenance, subscribers, domains |
| **Email Testing** | create address, wait (≤25 s), latest, list/get messages, source, OTP codes, links, inject; domains list, get, create, update, verify, activity |
| **Webhook Testing** | inboxes list, get, create, update, activity; wait (≤25 s), latest, list/get events |

Delete, publish and rollback return `{status: "confirmation_required", changes, confirmationToken}` first; call again with `confirmation_token` after the user agrees. Tokens are HMACs signed by the server process (set `DEVHELM_MCP_CONFIRMATION_SECRET` so every replica shares the key) and last 15 minutes. Errors come back as `isError` with every `ErrorResponse` field and a sentence for the agent.

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
