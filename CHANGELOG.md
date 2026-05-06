# Changelog

All notable changes to `devhelm-mcp-server` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.2] — 2026-05-06

### Changed

- Bump `devhelm` Python SDK floor to `>=0.7.2`. Older versions raise Pydantic
  `extra_forbidden` on the new `managedBy` field that the API now returns on
  resource DTOs.

## [0.8.1] — 2026-05-06

### Changed

- Sync OpenAPI spec and refresh bundled SDK to pick up the new monitor
  validation contract (`frequencySeconds` bounds, dynamic region whitelist)
  and `managedBy` resource-attribution field.

## [0.8.0] — 2026-05-06

### Added

- **Maintenance window tools** (`maintenance_window_*`): list / create / get
  / update / cancel scheduled maintenance windows so AI agents can suppress
  alerts during planned deploys.

## [0.7.1] — 2026-05-06

### Fixed

- `--help` / `--version` no longer hang waiting on stdin. The binary now ships
  a proper `argparse` interface with `--transport {stdio,http}`, `--host`,
  `--port` flags. (Also addressable via `DEVHELM_MCP_TRANSPORT`,
  `DEVHELM_MCP_HOST`, `DEVHELM_MCP_PORT` env vars.)
- ASCII banner suppressed on stdio transport so it doesn't pollute JSON-RPC.
- `/mcp` (no trailing slash) is rewritten in-process instead of returning a
  `307` redirect (which not all MCP clients follow correctly).
- `serverInfo` now reports `name=devhelm-mcp-server`, `version=<package>`
  (was the FastMCP runtime `name=DevHelm`, `version=3.x.y`). Makes support
  triage unambiguous and lets clients pin behavior to a published wheel.

## [0.7.0] — 2026-05-05

### **Breaking**

- **Tool input schemas no longer accept `api_token`.** Authentication is
  resolved at the transport layer:
  - Hosted Streamable HTTP: `Authorization: Bearer <token>` header.
  - Stdio: `DEVHELM_API_TOKEN` environment variable.
  This eliminates the per-call token-passing friction that made the server
  awkward in Cursor / Claude Desktop. Existing clients that still pass
  `api_token` in tool arguments will get an `unexpected_keyword_argument`
  Pydantic error from FastMCP.

- **`create_monitor` no longer accepts a caller-supplied `managedBy`.**
  The server forces `managedBy=MCP` on every monitor it creates so resource
  attribution is honest. Callers that need a different attribution should
  use the SDK or CLI directly.

- **`delete_monitor` parameter renamed:** `id` → `monitor_id`. (Same shape
  applied across other resource delete tools — `incident_id`,
  `channel_id`, etc. for consistency.)

- **`list_*` tools no longer require an empty `body: {}` envelope.** Pass
  no arguments instead.

### Fixed

- Upstream API failures now surface as `isError: true` ToolError responses
  instead of being swallowed silently.
- Documented user journeys end-to-end now actually work without hand-tuning.

### Added

- Usage telemetry now reports `surface=mcp` so we can tell MCP traffic from
  raw SDK traffic in dashboards.

## [0.6.0] — 2026-05-04

Initial public release with 101 tools covering monitors, incidents, alert
channels, notification policies, environments, secrets, tags, resource
groups, webhooks, API keys, service dependencies, deploy locks, status
pages, and dashboard read.
