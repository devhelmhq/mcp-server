#!/usr/bin/env bash
#
# Regenerate against an arbitrary OpenAPI spec for the spec-evolution harness.
#
# Usage: scripts/regen-from.sh <path-to-spec.json>
#
# mcp-server has no codegen of its own — all its types come from the
# `devhelm` SDK. So "regenerating mcp-server from a mutated spec" means:
#
#   1. copy the mutated spec into mcp-server's own vendored docs/openapi/
#      (for parity tests + the spec-check workflow that fires on
#      `spec_updated` repository_dispatch from mono)
#   2. delegate to ../sdk-python/scripts/regen-from.sh so the locally-
#      tracked SDK rebuilds with the mutated spec
#   3. force uv to re-link the SDK into mcp-server's venv so the next
#      Python import sees the new generated code
#
# Prints absolute path to the regenerated mcp-server source root on stdout.
#
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <path-to-spec.json>" >&2
  exit 1
fi

INPUT_SPEC="$1"
if [[ ! -f "$INPUT_SPEC" ]]; then
  echo "error: spec not found at $INPUT_SPEC" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_SPEC="$ROOT_DIR/docs/openapi/monitoring-api.json"
SDK_PYTHON_DIR="$ROOT_DIR/../sdk-python"
OUTPUT="$ROOT_DIR/src/devhelm_mcp"

# Skip the copy when the caller passes the vendored spec back in (harness
# post-session teardown re-regens from the restored baseline).
INPUT_ABS="$(cd "$(dirname "$INPUT_SPEC")" && pwd)/$(basename "$INPUT_SPEC")"
TARGET_ABS="$(cd "$(dirname "$TARGET_SPEC")" && pwd)/$(basename "$TARGET_SPEC")"
if [[ "$INPUT_ABS" != "$TARGET_ABS" ]]; then
  cp "$INPUT_SPEC" "$TARGET_SPEC"
fi

if [[ ! -x "$SDK_PYTHON_DIR/scripts/regen-from.sh" ]]; then
  echo "error: sibling sdk-python missing or regen-from.sh not executable: $SDK_PYTHON_DIR" >&2
  exit 1
fi

# Regenerate the upstream SDK from the same mutated spec.
# `uv run` resolves the project from cwd by default — explicitly chdir
# into sdk-python so it picks up *that* project's venv (with
# datamodel-codegen) instead of mcp-server's runtime-only venv.
( cd "$SDK_PYTHON_DIR" && "$SDK_PYTHON_DIR/scripts/regen-from.sh" "$INPUT_SPEC" >&2 )

# Force uv to relink the local SDK into mcp-server's venv. We can't use
# `uv sync` here: pyproject pins `devhelm` to a git branch via
# `tool.uv.sources`, so `uv sync` would either no-op (if the locked git
# commit is already installed) or re-fetch from git, both ignoring our
# locally-regenerated source. `uv pip install --force-reinstall --no-deps`
# bypasses the lockfile and unconditionally copies the local source into
# site-packages. Callers using this venv must pass `uv run --no-sync` to
# avoid `uv run`'s implicit pre-execution sync, which would otherwise
# re-resolve the lockfile and clobber the relink. Failures must surface —
# a silently un-relinked SDK would cause the mono evolution harness to
# test stale generated code.
cd "$ROOT_DIR"
uv pip install --quiet --force-reinstall --no-deps "$SDK_PYTHON_DIR" >&2

echo "$OUTPUT"
