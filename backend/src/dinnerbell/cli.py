"""The `dinnerbell` command (serve, check-config, migrate, backup, inspect, openapi)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dinnerbell.boot import EXIT_CONFIG, BootError, prepare
from dinnerbell.core.clock import SystemClock
from dinnerbell.core.config import ConfigError, Settings, load_settings
from dinnerbell.core.logging import configure_logging, get_logger

log = get_logger(__name__)

# Placeholder settings that let `openapi` build the app without any environment.
_SCHEMA_SETTINGS: dict[str, Any] = {
    "app_base_url": "http://localhost:8080",
    "app_secret_key": "schema-generation-only-" + "x" * 16,
    "app_password": "schema-generation-only",
    "tz": "UTC",
}


def _settings_or_exit() -> Settings:
    try:
        return load_settings()
    except ConfigError as exc:
        print("Dinner Bell can't start because of its configuration:", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        print("See .env.example for every setting.", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from None


def _boot_or_exit(settings: Settings) -> None:
    try:
        prepare(settings, SystemClock())
    except BootError as failure:
        log.error("boot.failed", exit_code=failure.exit_code, reason=failure.message)
        raise SystemExit(failure.exit_code) from None


def cmd_serve(args: argparse.Namespace) -> None:
    settings = _settings_or_exit()
    configure_logging(settings.log_level, secret_literals=settings.secret_literals())
    for warning in settings.warnings():
        log.warning("config.warning", detail=warning)
    import uvicorn

    if args.reload:
        uvicorn.run(
            "dinnerbell.devserver:create",
            factory=True,
            reload=True,
            reload_dirs=[str(Path(__file__).parent)],
            host=args.host,
            port=settings.port,
            log_config=None,
            access_log=False,
        )
        return
    _boot_or_exit(settings)
    from dinnerbell.app import create_app

    uvicorn.run(
        create_app(settings),
        host=args.host,
        port=settings.port,
        proxy_headers=bool(settings.trusted_proxies),
        forwarded_allow_ips=",".join(settings.trusted_proxies) or None,
        access_log=False,
        server_header=False,
        timeout_graceful_shutdown=10,
        log_config=None,
    )


def cmd_check_config(args: argparse.Namespace) -> None:
    settings = _settings_or_exit()
    for warning in settings.warnings():
        print(f"warning: {warning}")
    print("Configuration OK.")


def cmd_migrate(args: argparse.Namespace) -> None:
    from dinnerbell.db import migrate

    settings = _settings_or_exit()
    configure_logging(settings.log_level, secret_literals=settings.secret_literals())
    current = migrate.current_revision(settings.db_path)
    head = migrate.head_revision()
    print(f"database revision: {current or 'none'}; head: {head}")
    if args.dry_run:
        return
    _boot_or_exit(settings)


def cmd_backup_now(args: argparse.Namespace) -> None:
    from dinnerbell.db import backup

    settings = _settings_or_exit()
    destination = settings.backup_dir / backup.nightly_name(
        SystemClock().now().astimezone(settings.zone).date()
    )
    result = backup.take_backup(settings.db_path, destination)
    print(f"wrote {result.path.name} ({result.bytes} bytes, {result.seconds}s)")


def cmd_inspect_backup(args: argparse.Namespace) -> None:
    from dinnerbell.db import backup

    print(json.dumps(backup.inspect_backup(Path(args.file)), indent=2))


def cmd_smoke_kroger(args: argparse.Namespace) -> None:
    import asyncio
    import os

    from dinnerbell.kroger import smoke

    raise SystemExit(asyncio.run(smoke.run(os.environ, sys.stdout)))


def cmd_openapi(args: argparse.Namespace) -> None:
    from dinnerbell.app import create_app

    app = create_app(Settings.model_validate(_SCHEMA_SETTINGS))
    schema = app.openapi()
    schema["info"]["version"] = "0"  # version bumps must not make the generated types stale
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dinnerbell", description="Dinner Bell server")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the app (backup + migrate first)")
    serve.add_argument("--reload", action="store_true", help="development auto-reload")
    serve.add_argument("--host", default="0.0.0.0")  # noqa: S104 - the container's listen address
    serve.set_defaults(func=cmd_serve)
    sub.add_parser("check-config", help="validate the environment").set_defaults(
        func=cmd_check_config
    )
    mig = sub.add_parser("migrate", help="back up and migrate, then exit")
    mig.add_argument("--dry-run", action="store_true", help="only show the revisions")
    mig.set_defaults(func=cmd_migrate)
    sub.add_parser("backup-now", help="write a verified backup").set_defaults(func=cmd_backup_now)
    inspect = sub.add_parser("inspect-backup", help="show a backup's revision and row counts")
    inspect.add_argument("file")
    inspect.set_defaults(func=cmd_inspect_backup)
    sub.add_parser(
        "smoke-kroger", help="a few real Kroger calls (needs KROGER_LIVE=1 and local keys)"
    ).set_defaults(func=cmd_smoke_kroger)
    openapi = sub.add_parser("openapi", help="print the OpenAPI schema")
    openapi.add_argument("--out")
    openapi.set_defaults(func=cmd_openapi)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
