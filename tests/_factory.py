"""Build valid instances of generated SDK models for unit tests.

Required fields get the simplest valid value for their type, so a test can
return a real ``RunDto`` from a mocked SDK call without hand-writing 40
fields.
"""

from __future__ import annotations

import types
import typing
import uuid
from datetime import UTC, date, datetime
from enum import Enum

from pydantic import AwareDatetime, BaseModel, NaiveDatetime, RootModel


def _value(tp: object) -> object:
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is typing.Annotated:
        return _value(args[0])
    if origin in (typing.Union, types.UnionType):
        non_null = [a for a in args if a is not type(None)]
        return _value(non_null[0])
    if origin is typing.Literal:
        return args[0]
    if origin in (list, tuple, set):
        return []
    if origin is dict:
        return {}
    if tp in (AwareDatetime, NaiveDatetime):
        return datetime(2026, 10, 25, tzinfo=UTC if tp is AwareDatetime else None)
    if isinstance(tp, type):
        if issubclass(tp, RootModel):
            return tp.model_validate(_value(tp.model_fields["root"].annotation))
        if issubclass(tp, BaseModel):
            return build(tp)
        if issubclass(tp, Enum):
            return next(iter(tp))
        if issubclass(tp, bool):
            return False
        if issubclass(tp, int):
            return 1
        if issubclass(tp, float):
            return 1.0
        if issubclass(tp, str):
            return "x"
        if issubclass(tp, uuid.UUID):
            return uuid.uuid4()
        if issubclass(tp, datetime):
            return datetime(2026, 10, 25, tzinfo=UTC)
        if issubclass(tp, date):
            return date(2026, 10, 25)
    return "x"


M = typing.TypeVar("M", bound=BaseModel)


def build(model: type[M], **overrides: object) -> M:
    data: dict[str, object] = {}
    for name, field in model.model_fields.items():
        if name in overrides:
            data[name] = overrides[name]
        elif field.is_required():
            data[name] = _value(field.annotation)
    return model.model_validate(data, by_name=True)
