"""Structured logging with secret redaction (docs/PLAN.md §10.6).

JSON when stdout isn't a terminal (the container), readable console output in development.
Every record, including uvicorn's and httpx's, passes through the redactor.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any, cast

import structlog

_SENSITIVE_KEY = re.compile(
    r"password|secret|token|authorization|cookie|code_verifier|^code$|refresh", re.IGNORECASE
)
_TOKENISH = re.compile(
    r"Bearer\s+[A-Za-z0-9._~+/=-]+"
    r"|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    r"|gAAAAA[A-Za-z0-9_=-]{20,}"
)
MASK = "***"


class Redactor:
    """structlog processor that masks sensitive keys, token-shaped strings and known secrets."""

    def __init__(self, literals: Iterable[str] = ()) -> None:
        self._literals = sorted({lit for lit in literals if len(lit) >= 6}, key=len, reverse=True)

    def scrub_text(self, text: str) -> str:
        for literal in self._literals:
            if literal in text:
                text = text.replace(literal, MASK)
        return _TOKENISH.sub(MASK, text)

    def _scrub(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.scrub_text(value)
        if isinstance(value, Mapping):
            mapping = cast(Mapping[Any, Any], value)
            return {
                key: (MASK if _SENSITIVE_KEY.search(str(key)) else self._scrub(item))
                for key, item in mapping.items()
            }
        if isinstance(value, list | tuple):
            items = cast(Iterable[Any], value)
            return [self._scrub(entry) for entry in items]
        return value

    def __call__(
        self, logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        for key in list(event_dict):
            if key in {"timestamp", "level", "logger"}:
                continue
            if key != "event" and _SENSITIVE_KEY.search(key):
                event_dict[key] = MASK
            else:
                event_dict[key] = self._scrub(event_dict[key])
        return event_dict


def _drop_color_message(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    event_dict.pop("color_message", None)  # uvicorn's ANSI-coloured duplicate of "event"
    return event_dict


def configure_logging(
    level: str = "INFO", *, json: bool | None = None, secret_literals: Iterable[str] = ()
) -> None:
    use_json = (not sys.stdout.isatty()) if json is None else json
    redactor = Redactor(secret_literals)
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.ExtraAdder(),
        _drop_color_message,
        redactor,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "aiosqlite", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # The access log would print query strings (e.g. an OAuth ?code=); we log requests ourselves.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(name)
    return logger
