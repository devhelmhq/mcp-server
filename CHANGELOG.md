# Changelog

All notable changes to `devhelm-mcp-server` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-06

First GA release. Cut alongside the `1.0.0` GA of the `devhelm` Python
SDK, the `devhelm` CLI, and the `@devhelm/sdk` JS/TS SDK. The schema
and tool surface that `0.8.3` shipped is the GA contract — no
behavioral changes from `0.8.3`, only the version bump and the SDK
floor change below.

### Changed

- Bump `devhelm` Python SDK floor to `>=1.0.0`. Aligns with the GA
  release of the SDK; future patch/minor SDK bumps will be picked up
  automatically without an explicit floor change here.

### Compatibility

- All tool input schemas, tool names, and response shapes are
  unchanged from `0.8.3`. Existing clients keep working without
  modification.

## [0.8.3] — 2026-05-06

### Changed

- Rewrite `initialize.instructions` to point at transport-layer auth
  (`Authorization: Bearer ...` for hosted, `DEVHELM_API_TOKEN` env for
  stdio) and explicitly note that tool schemas no longer accept
  `api_token` arguments. The previous wording ("All operations require
  a valid DevHelm API token") contradicted the 0.7.0 schema change and
  caused LLMs to attempt to thread tokens into tool args.
- Add `CHANGELOG.md` retroactively covering 0.6.0 → 0.8.x. Going
  forward, every release lands with a corresponding stanza.

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
