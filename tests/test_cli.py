"""Tests for the ``devhelm-mcp-server`` CLI parser.

Before this PR the entry point had no parser at all, so ``--help`` was
silently consumed and the server booted in stdio mode — users had no
way to discover the flags or the HTTP transport. We exercise the parser
directly here (no subprocess spawn) so the help text is fast to assert
and so we don't have to install the wheel inside the test runner.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

from devhelm_mcp.server import (
    _build_arg_parser,
    _resolve_host,
    _resolve_port,
    _resolve_transport,
    main,
)

# --------------------------------------------------------------------------- #
# Argparse surface
# --------------------------------------------------------------------------- #


class TestArgParser:
    def test_help_exits_zero_and_prints_usage(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        parser = _build_arg_parser()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["--help"])
        # argparse exits 0 on --help, non-zero on argument errors. We
        # assert on the exact code so a future "always exit 1 on help"
        # regression is caught.
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert "devhelm-mcp-server" in out
        assert "--transport" in out
        assert "--host" in out
        assert "--port" in out
        assert "--version" in out
        # Examples block must mention both stdio (env-driven) and http.
        assert "DEVHELM_API_TOKEN" in out
        assert "stdio" in out
        assert "http" in out

    def test_version_prints_package_version_and_exits_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        parser = _build_arg_parser()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["--version"])
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert out.startswith("devhelm-mcp-server ")

    def test_unknown_flag_exits_with_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Sanity — argparse should reject unknown flags rather than
        # silently passing them to mcp.run() (which is what happened
        # before the parser existed).
        parser = _build_arg_parser()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["--made-up-flag"])
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "unrecognized" in err.lower() or "invalid" in err.lower()


# --------------------------------------------------------------------------- #
# Resolution helpers — flag wins, env var fallback, default last
# --------------------------------------------------------------------------- #


class TestResolveTransport:
    def test_flag_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVHELM_MCP_TRANSPORT", "http")
        assert _resolve_transport("stdio") == "stdio"

    def test_env_when_no_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVHELM_MCP_TRANSPORT", "http")
        assert _resolve_transport(None) == "http"

    def test_default_stdio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEVHELM_MCP_TRANSPORT", raising=False)
        assert _resolve_transport(None) == "stdio"

    def test_invalid_value_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVHELM_MCP_TRANSPORT", "carrier-pigeon")
        with pytest.raises(SystemExit):
            _resolve_transport(None)


class TestResolveHostAndPort:
    def test_host_flag_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVHELM_MCP_HOST", "10.0.0.1")
        assert _resolve_host("127.0.0.1") == "127.0.0.1"

    def test_host_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEVHELM_MCP_HOST", raising=False)
        monkeypatch.setenv("HOST", "10.0.0.5")
        assert _resolve_host(None) == "10.0.0.5"

    def test_host_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEVHELM_MCP_HOST", raising=False)
        monkeypatch.delenv("HOST", raising=False)
        assert _resolve_host(None) == "0.0.0.0"

    def test_port_flag_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVHELM_MCP_PORT", "9999")
        assert _resolve_port(8080) == 8080

    def test_port_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVHELM_MCP_PORT", "9999")
        assert _resolve_port(None) == 9999

    def test_port_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEVHELM_MCP_PORT", raising=False)
        monkeypatch.delenv("PORT", raising=False)
        assert _resolve_port(None) == 8000


# --------------------------------------------------------------------------- #
# main() — keeps existing default behavior, dispatches to the right backend
# --------------------------------------------------------------------------- #


class TestMainDispatch:
    def test_no_args_runs_stdio_transport(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Drop any leftover env that would steer us off stdio.
        for key in ("DEVHELM_MCP_TRANSPORT", "DEVHELM_MCP_HOST", "DEVHELM_MCP_PORT"):
            monkeypatch.delenv(key, raising=False)
        with (
            patch("devhelm_mcp.server.mcp.run") as run,
            patch("uvicorn.run") as uvi_run,
        ):
            main([])
            run.assert_called_once_with()
            uvi_run.assert_not_called()

    def test_transport_http_invokes_uvicorn_with_resolved_host_port(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DEVHELM_MCP_HOST", raising=False)
        monkeypatch.delenv("DEVHELM_MCP_PORT", raising=False)
        monkeypatch.delenv("HOST", raising=False)
        monkeypatch.delenv("PORT", raising=False)
        with patch("uvicorn.run") as uvi_run, patch("devhelm_mcp.server.mcp.run"):
            main(["--transport", "http", "--host", "127.0.0.1", "--port", "8080"])
        assert uvi_run.call_count == 1
        kwargs: dict[str, Any] = uvi_run.call_args.kwargs
        assert uvi_run.call_args.args == ("devhelm_mcp.server:app",)
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8080
        # Production-critical: TLS-aware proxy headers must stay on so
        # the ``/mcp`` → ``/mcp/`` redirect doesn't downgrade clients
        # off HTTPS (END-1186).
        assert kwargs["proxy_headers"] is True
        assert kwargs["forwarded_allow_ips"] == "*"

    def test_env_transport_http_still_honored_without_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Existing K8s deploy sets DEVHELM_MCP_TRANSPORT=http with no
        # flags; the parser must not regress that path.
        monkeypatch.setenv("DEVHELM_MCP_TRANSPORT", "http")
        monkeypatch.delenv("DEVHELM_MCP_HOST", raising=False)
        monkeypatch.delenv("DEVHELM_MCP_PORT", raising=False)
        monkeypatch.delenv("HOST", raising=False)
        monkeypatch.delenv("PORT", raising=False)
        with patch("uvicorn.run") as uvi_run, patch("devhelm_mcp.server.mcp.run"):
            main([])
        assert uvi_run.call_count == 1
        # Defaults preserved when no host/port flag is passed.
        assert uvi_run.call_args.kwargs["host"] == "0.0.0.0"
        assert uvi_run.call_args.kwargs["port"] == 8000

    def test_help_flag_via_main_exits_without_starting_transport(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch("devhelm_mcp.server.mcp.run") as run,
            patch("uvicorn.run") as uvi_run,
        ):
            with pytest.raises(SystemExit) as excinfo:
                main(["--help"])
            assert excinfo.value.code == 0
            run.assert_not_called()
            uvi_run.assert_not_called()
        out = capsys.readouterr().out
        assert "devhelm-mcp-server" in out


# --------------------------------------------------------------------------- #
# Cross-check: the package metadata used by --version is real
# --------------------------------------------------------------------------- #


def test_package_version_lookup_returns_string() -> None:
    from devhelm_mcp.server import _package_version

    assert isinstance(_package_version(), str)
    # Either the real installed version, or the source-tree fallback.
    assert _package_version() != ""


def test_dev_pyproject_version_matches_pkg_metadata() -> None:
    """Sanity: the wheel built from this tree exposes the same version
    that --version reports. Skipped when running from a pip install
    where the on-disk pyproject doesn't apply."""
    from devhelm_mcp.server import _package_version

    pyproject = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pyproject.toml"
    )
    if not os.path.isfile(pyproject):
        pytest.skip("pyproject.toml not present")
    with open(pyproject) as f:
        text = f.read()
    import re

    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        pytest.skip("couldn't parse version from pyproject.toml")
    assert _package_version() in (m.group(1), "unknown")
