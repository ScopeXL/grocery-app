"""Settings come from environment variables only (docs/PLAN.md §11.2).

Problems are reported by variable *name*, never by value, so a misconfigured secret can't
end up in a log. The CLI prints the report and exits with code 78.
"""

from __future__ import annotations

import ipaddress
import os
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import Annotated, Any, ClassVar
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PLACEHOLDER_SECRET = "change-me-to-a-long-random-string"  # noqa: S105 - the documented placeholder
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
KROGER_CALLBACK_PATH = "/api/kroger/callback"


class KrogerMode(StrEnum):
    LIVE = "live"
    FAKE = "fake"


class ConfigError(Exception):
    """Raised with a list of human-readable problems; each names a variable, never a value."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    app_base_url: str
    app_secret_key: SecretStr
    app_password: SecretStr
    tz: str
    port: int = Field(default=8080, ge=1024, le=65535)
    trusted_proxies: Annotated[tuple[str, ...], NoDecode] = ()
    kroger_mode: KrogerMode = KrogerMode.FAKE
    kroger_client_id: SecretStr | None = None
    kroger_client_secret: SecretStr | None = None
    kroger_redirect_uri: str | None = None
    log_level: str = "INFO"
    data_dir: Path = Path("/data")
    data_dir_unsafe_fs_ok: bool = False
    dinnerbell_test_mode: bool = False
    dinnerbell_container: bool = False
    dinnerbell_static_dir: Path | None = None

    _LOG_LEVELS: ClassVar[frozenset[str]] = frozenset(
        {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    )

    @field_validator("app_base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        parts = urlsplit(value.strip())
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("must be an origin like https://dinner.example.com")
        if parts.path not in {"", "/"} or parts.query or parts.fragment:
            raise ValueError("must be an origin only, with no path, query or fragment")
        if parts.scheme == "http" and parts.hostname not in LOCAL_HOSTS:
            raise ValueError("must use https unless it is localhost")
        return f"{parts.scheme}://{parts.netloc}"

    @field_validator("app_secret_key")
    @classmethod
    def _check_secret_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw == PLACEHOLDER_SECRET:
            raise ValueError("is still the placeholder; generate one with: openssl rand -base64 48")
        if len(raw) < 32:
            raise ValueError("must be at least 32 characters (openssl rand -base64 48)")
        return value

    @field_validator("app_password")
    @classmethod
    def _check_password(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 12:
            raise ValueError("must be at least 12 characters (use a passphrase)")
        return value

    @field_validator("tz")
    @classmethod
    def _check_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("must be an IANA time zone such as America/New_York") from exc
        return value

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def _split_proxies(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("trusted_proxies")
    @classmethod
    def _check_proxies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for entry in value:
            if entry == "*":
                raise ValueError("must list specific IPs or CIDRs, not *")
            try:
                network = ipaddress.ip_network(entry, strict=False)
            except ValueError as exc:
                raise ValueError("must be a comma-separated list of IPs or CIDRs") from exc
            if network.prefixlen == 0:
                raise ValueError("must not trust every address (0.0.0.0/0 or ::/0)")
        return value

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in cls._LOG_LEVELS:
            raise ValueError("must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")
        return upper

    @model_validator(mode="after")
    def _check_cross_fields(self) -> Settings:
        if self.kroger_mode is KrogerMode.LIVE and not (
            self.kroger_client_id and self.kroger_client_secret
        ):
            raise ValueError("KROGER_MODE=live needs KROGER_CLIENT_ID and KROGER_CLIENT_SECRET")
        if self.kroger_redirect_uri and self.kroger_redirect_uri != self.expected_redirect_uri:
            raise ValueError("KROGER_REDIRECT_URI must equal APP_BASE_URL + /api/kroger/callback")
        if self.dinnerbell_test_mode and not self.is_localhost:
            raise ValueError("DINNERBELL_TEST_MODE is only allowed when APP_BASE_URL is localhost")
        return self

    # ---- derived values -------------------------------------------------------------------

    @cached_property
    def _parts(self):
        return urlsplit(self.app_base_url)

    @property
    def is_https(self) -> bool:
        return self._parts.scheme == "https"

    @property
    def is_localhost(self) -> bool:
        return (self._parts.hostname or "") in LOCAL_HOSTS

    @property
    def expected_redirect_uri(self) -> str:
        return self.app_base_url + KROGER_CALLBACK_PATH

    @property
    def cookie_name(self) -> str:
        # The __Host- prefix requires Secure, Path=/ and no Domain, so it only works on https.
        return "__Host-dinnerbell" if self.is_https else "dinnerbell"

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "dinnerbell.db"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def lock_path(self) -> Path:
        return self.data_dir / ".lock"

    def secret_literals(self) -> list[str]:
        """Exact secret values, so log redaction can scrub them wherever they appear."""
        values = [self.app_secret_key.get_secret_value(), self.app_password.get_secret_value()]
        if self.kroger_client_secret:
            values.append(self.kroger_client_secret.get_secret_value())
        return [v for v in values if v]

    def warnings(self, environ: dict[str, str] | None = None) -> list[str]:
        """Non-fatal problems worth a log line (typos in variable names, missing proxy list)."""
        env = os.environ if environ is None else environ
        known = {name.upper() for name in type(self).model_fields}
        found: list[str] = []
        for name in sorted(env):
            upper = name.upper()
            if upper.startswith(("APP_", "KROGER_")) and upper not in known:
                if upper in {"KROGER_LIVE", "KROGER_SMOKE_ZIP"}:
                    continue  # used only by the local smoke test
                found.append(f"{name} is not a setting Dinner Bell knows (typo?)")
        if self.is_https and not self.trusted_proxies:
            found.append(
                "TRUSTED_PROXIES is empty: behind a reverse proxy, client IPs and https "
                "detection will be wrong (see Settings → Connection → Diagnostics)"
            )
        return found


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    """Build Settings from the environment, turning every problem into a name-only message."""
    try:
        if environ is None:
            return Settings()  # pyright: ignore[reportCallIssue]
        return Settings.model_validate(_lower_keys(environ))
    except ValidationError as exc:
        raise ConfigError(_describe(exc)) from None


def _lower_keys(environ: dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in environ.items()}


def _describe(exc: ValidationError) -> list[str]:
    problems: list[str] = []
    for error in exc.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in error["loc"]) or "settings"
        name = location.upper() if error["loc"] else ""
        message = str(error["msg"])
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        if error["type"] == "missing":
            message = "is required"
        problems.append(f"{name} {message}".strip())
    return problems
