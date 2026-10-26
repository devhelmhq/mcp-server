"""MCP tool envelopes. Each one composes generated SDK models (doc 42 §5.1.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from devhelm import (
    DefinitionHeadDto,
    FilesCode,
    MonitorDto,
    MonitorTestResultDto,
    RevisionDto,
    RunArtifactDto,
    RunConsoleDto,
    RunFailureDto,
    RunStepDto,
)
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")

#: Inline code limit per call; the server's bundle limit is 5 MB / 256 files.
MAX_INLINE_CODE_BYTES = 1024 * 1024


class _Out(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True
    )


class CodeFiles(BaseModel):
    """A check's source held inline. No filesystem access."""

    model_config = ConfigDict(extra="forbid")

    entrypoint: str = Field(description="File that runs, e.g. checkout.spec.ts")
    files: dict[str, str] = Field(
        description="Bundle-relative path to UTF-8 file text, including the "
        "entrypoint (1 MB per call; bundles are capped at 5 MB / 256 files)"
    )
    include: list[str] | None = Field(
        default=None,
        description="Paths in files that ship although nothing imports them "
        "(fixtures, data)",
    )

    def as_code(self) -> FilesCode:
        code: FilesCode = {"entrypoint": self.entrypoint, "files": self.files}
        if self.include:
            code["include"] = self.include
        return code


class RunEnvelope(_Out):
    """One run, shaped for an agent. Every run-producing tool returns it."""

    run_id: UUID
    phase: str
    outcome: str | None = None
    flaky: bool | None = None
    headline: str | None = None
    failure: RunFailureDto | None = None
    steps: list[RunStepDto] = Field(default_factory=list)
    artifacts: list[RunArtifactDto] = Field(default_factory=list)
    run_url: str | None = Field(default=None)
    start_deadline_at: datetime | None = Field(default=None)
    next_action: str


class TriggerEnvelope(_Out):
    trigger_id: UUID
    billed_runs: int
    runs: list[RunEnvelope]
    next_action: str


class ProbeResult(_Out):
    """``test_monitor`` on an uptime monitor (deprecated until 2027-01-31)."""

    probe: MonitorTestResultDto
    deprecation: str


class CursorPageOut(_Out, Generic[T]):
    data: list[T]
    next_cursor: str | None = Field(default=None)
    has_more: bool = Field(default=False)


class PageOut(_Out, Generic[T]):
    data: list[T]
    has_next: bool = Field(default=False)
    has_prev: bool = Field(default=False)
    total_elements: int | None = Field(default=None)
    total_pages: int | None = Field(default=None)


class TextFiles(_Out):
    """Revision source files, capped at 64 KB of text in total."""

    entrypoint: str
    files: dict[str, str]
    truncated: bool = False
    omitted: list[str] = Field(
        default_factory=list,
        description="Paths left out to stay under the cap; ask for one with path=",
    )


class ConsoleOut(_Out):
    """Console output trimmed to fit the 64 KB tool cap."""

    console: RunConsoleDto
    truncated: bool = False
    omitted_groups: int = 0
    omitted_lines: int = 0


class ConfirmationRequired(_Out, Generic[T]):
    status: Literal["confirmation_required"] = "confirmation_required"
    changes: list[str]
    preview: T
    confirmation_token: str
    expires_at: datetime
    next_action: str


class PublishPreview(_Out):
    monitor: MonitorDto
    revision: RevisionDto


class Published(_Out):
    status: Literal["published"] = "published"
    head: DefinitionHeadDto


class RolledBack(_Out):
    status: Literal["rolled_back"] = "rolled_back"
    head: DefinitionHeadDto


class Deleted(_Out):
    status: Literal["deleted"] = "deleted"
    monitor_id: str
    next_action: str


class Done(_Out):
    """A write with no response body (discard, secret value set)."""

    status: Literal["ok"] = "ok"
    message: str


class Declined(_Out):
    """The human declined to give a value; nothing was written."""

    status: Literal["declined"] = "declined"
    message: str


class SecretValueLink(_Out):
    """No elicitation support: the human sets the value in the dashboard."""

    status: Literal["needs_human"] = "needs_human"
    url: str
    message: str


__all__ = [
    "MAX_INLINE_CODE_BYTES",
    "CodeFiles",
    "ConfirmationRequired",
    "ConsoleOut",
    "CursorPageOut",
    "Declined",
    "Deleted",
    "Done",
    "PageOut",
    "ProbeResult",
    "PublishPreview",
    "Published",
    "RolledBack",
    "RunEnvelope",
    "SecretValueLink",
    "TextFiles",
    "TriggerEnvelope",
]
