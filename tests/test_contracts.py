"""Contract tests: bundle conformance vectors and the no-``Any`` rule.

The vectors are vendored from mono ``docs/contracts/bundle-vectors.json``.
MCP sends inline files through the SDK, so the upload digest of every
vector's file map must equal the server's (doc 42 §5.3).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from devhelm._bundle import collect

from devhelm_mcp._models import CodeFiles

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "docs/contracts/bundle-vectors.json").read_text())


def _cases() -> list[dict[str, object]]:
    return [
        v
        for v in VECTORS["vectors"]
        if "refusal" not in v["expect"]
        and "binaryFiles" not in v["request"]
        and "entrypoint" in v["request"]
    ]


@pytest.mark.parametrize("vector", _cases(), ids=lambda v: str(v["name"]))
def test_inline_files_hash_like_the_server(vector: dict[str, object]) -> None:
    request = vector["request"]
    expect = vector["expect"]
    assert isinstance(request, dict) and isinstance(expect, dict)
    code = CodeFiles(
        entrypoint=request["entrypoint"],
        files=request["files"],
        include=request.get("include"),
    )
    assert collect(code.as_code()).digest == expect["uploadDigest"]


# The modules written on the typed tool layer. The older modules still use
# ``dict[str, Any]`` results (see the PR's "Not in this PR").
TYPED_MODULES = [
    "_tooling.py",
    "_models.py",
    "_runs.py",
    "_confirm.py",
    "tools/monitors.py",
    "tools/revisions.py",
    "tools/runs.py",
    "tools/account.py",
    "tools/secrets.py",
    "tools/incidents.py",
]


@pytest.mark.parametrize("module", TYPED_MODULES)
def test_no_any_in_typed_modules(module: str) -> None:
    tree = ast.parse((ROOT / "src/devhelm_mcp" / module).read_text())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "Any" not in names | attrs
