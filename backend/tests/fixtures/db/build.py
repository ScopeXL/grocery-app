"""Build a synthetic fixture database for a released migration revision (CLAUDE.md rule 4).

Every release adds `tests/fixtures/db/<revision>.sql`: the schema at that release plus a few
synthetic rows in every table. `tests/test_migrations.py` replays each file and migrates it to
head, so a new migration can't break a real household's data.

    cd backend && uv run python -m tests.fixtures.db.build 202610062123

Only synthetic values: "Sample Parent", location 99999001, UPCs 00000000000NN, made-up IDs.
Seeds never change once their file is committed; a new release adds a new entry.
"""

# Only this file's own constant IDs are interpolated into the seed SQL.
# ruff: noqa: S608

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

from alembic import command

from dinnerbell.db import migrate

HERE = Path(__file__).parent

# A statement, or a statement with `?` parameters (for blobs and JSON payloads).
Statement = str | tuple[str, tuple[object, ...]]

P1 = "00000000-0000-7000-8000-000000000001"  # Sample Parent
STORE = "00000000-0000-7000-8000-000000000101"
PHOTO = "00000000-0000-7000-8000-000000000201"
BEEF, BANANAS, OIL, CANDLES = (f"00000000-0000-7000-8000-00000000030{n}" for n in range(1, 5))
TACOS, RICE, OLD_SOUP = (f"00000000-0000-7000-8000-00000000040{n}" for n in range(1, 4))

# Members and devices: every release has them.
_PEOPLE: list[Statement] = [
    "INSERT INTO members (id, name, marker_color, sort, created_at, archived_at) VALUES "
    f"('{P1}', 'Sample Parent', 'basil', 0, '2026-10-06 12:00:00', NULL), "
    "('00000000-0000-7000-8000-000000000002', 'Sample Kid', 'tomato', 1, "
    "'2026-10-06 12:01:00', NULL), "
    "('00000000-0000-7000-8000-000000000003', 'Sample Guest', 'plum', 2, "
    "'2026-10-06 12:02:00', '2026-10-06 13:00:00')",
    "INSERT INTO devices (id, label, member_id, created_at, last_seen_at, revoked_at) VALUES "
    f"('00000000-0000-7000-8000-0000000000d1', 'iPhone', '{P1}', '2026-10-06 12:00:00', "
    "'2026-10-06 12:30:00', NULL), "
    "('00000000-0000-7000-8000-0000000000d2', 'Android phone', NULL, "
    "'2026-10-06 12:05:00', '2026-10-06 12:06:00', '2026-10-06 12:40:00')",
]


def _tiny_webp(size: tuple[int, int]) -> bytes:
    from PIL import Image

    out = BytesIO()
    Image.new("RGB", size, (200, 170, 90)).save(out, "WEBP", quality=40)
    return out.getvalue()


def _cached_beef() -> str:
    """A cache row as 0.2.0 wrote it (kroger.parse.product_to_json); synthetic values."""
    return json.dumps(
        {
            "product_id": "0000000000001",
            "upc": "0000000000001",
            "description": "Sample Ground Beef",
            "brand": "Sample",
            "categories": ["Meat & Seafood"],
            "page_uri": "/p/sample-ground-beef/0000000000001",
            "image": None,
            "size": "1 lb",
            "sold_by": "UNIT",
            "price": {
                "regular": 549,
                "promo": 499,
                "each_estimate": None,
                "effective": "2026-10-01T04:00:00+00:00",
                "expires": "2026-10-08T03:59:59+00:00",
            },
            "stock_level": "HIGH",
            "in_store": True,
            "aisles": [{"number": None, "side": None, "description": "MEAT", "bay": None}],
        },
        separators=(",", ":"),
    )


def _m1() -> list[Statement]:
    """0.2.0 (M1): a store and its sections, items, dishes and their lines, a photo, Kroger
    cache and usage rows."""
    return [
        "UPDATE household SET name = 'Sample household', updated_at = '2026-10-06 12:10:00', "
        f"active_store_id = '{STORE}'",
        "UPDATE app_meta SET auth_epoch = 3, last_boot_version = '0.2.0'",
        *_PEOPLE,
        "INSERT INTO stores (id, location_id, chain, name, address_line1, address_line2, city, "
        "state, zip_code, timezone, chain_domain, departments, created_at, updated_at) VALUES "
        f"('{STORE}', '99999001', 'SAMPLE MARKET', 'Sample Market Downtown', "
        "'100 Sample Street', NULL, 'Sampleton', 'ST', '00001', 'America/New_York', NULL, "
        """'["Produce","Bakery","Deli"]', '2026-10-06 12:10:00', '2026-10-06 12:10:00')""",
        "INSERT INTO store_sections (id, store_id, key, label, sort_index, hidden) VALUES "
        f"('00000000-0000-7000-8000-000000000111', '{STORE}', 'cat:produce', 'Produce', 100, 0), "
        f"('00000000-0000-7000-8000-000000000112', '{STORE}', 'aisle:12', 'Aisle 12', 1012, 0), "
        f"('00000000-0000-7000-8000-000000000113', '{STORE}', 'cat:other', 'Other', 9900, 1)",
        (
            "INSERT INTO photos (id, webp, thumb, width, height, created_at) "
            "VALUES (?, ?, ?, 4, 3, '2026-10-06 12:20:00')",
            (PHOTO, _tiny_webp((4, 3)), _tiny_webp((2, 2))),
        ),
        "INSERT INTO items (id, name, product_id, upc, size_text, size_source, sold_by, "
        "each_weight_lb, is_staple, section_override_key, created_at, updated_at, archived_at) "
        "VALUES "
        f"('{BEEF}', 'Ground beef', '0000000000001', '0000000000001', '1 lb', 'parsed', "
        "'UNIT', NULL, 0, NULL, '2026-10-06 12:30:00', '2026-10-06 12:30:00', NULL), "
        f"('{BANANAS}', 'Bananas', '0000000000002', '0000000000002', NULL, 'parsed', "
        "'WEIGHT', '3/8', 0, NULL, '2026-10-06 12:31:00', '2026-10-06 12:31:00', NULL), "
        f"('{OIL}', 'Cooking oil', '0000000000003', '0000000000003', '48 fl oz', 'household', "
        "'UNIT', NULL, 1, 'aisle:12', '2026-10-06 12:32:00', '2026-10-06 12:32:00', NULL), "
        f"('{CANDLES}', 'Birthday candles', NULL, NULL, NULL, 'parsed', NULL, NULL, 0, NULL, "
        "'2026-10-06 12:33:00', '2026-10-06 12:33:00', '2026-10-06 13:00:00')",
        "INSERT INTO dishes (id, name, role, occasions, servings, photo_id, notes, recipe_url, "
        "favorite, last_planned_at, created_at, updated_at, archived_at) VALUES "
        f"""('{TACOS}', 'Tacos', 'main', '["dinner"]', 4, '{PHOTO}', 'Warm the shells.', """
        "'https://example.com/tacos', 1, NULL, '2026-10-06 12:40:00', '2026-10-06 12:40:00', "
        "NULL), "
        f"""('{RICE}', 'Rice', 'side', '["dinner","lunch"]', NULL, NULL, NULL, NULL, 0, NULL, """
        "'2026-10-06 12:41:00', '2026-10-06 12:41:00', NULL), "
        f"""('{OLD_SOUP}', 'Soup', 'main', '[]', NULL, NULL, NULL, NULL, 0, NULL, """
        "'2026-10-06 12:42:00', '2026-10-06 12:42:00', '2026-10-06 13:10:00')",
        "INSERT INTO dish_items (id, dish_id, item_id, amount_kind, amount, unit, position) "
        "VALUES "
        f"('00000000-0000-7000-8000-000000000501', '{TACOS}', '{BEEF}', 'packages', '1', "
        "NULL, 0), "
        f"('00000000-0000-7000-8000-000000000502', '{TACOS}', '{BANANAS}', 'count', '2', "
        "NULL, 1), "
        f"('00000000-0000-7000-8000-000000000503', '{RICE}', '{OIL}', 'measure', '1', "
        "'tbsp', 0), "
        f"('00000000-0000-7000-8000-000000000504', '{OLD_SOUP}', '{OIL}', 'measure', '1/3', "
        "'cup', 0)",
        (
            "INSERT INTO kroger_product_cache (product_id, location_id, payload, fetched_at, "
            "expires_at, cache_control_raw) VALUES ('0000000000001', '99999001', ?, "
            "'2026-10-06 12:50:00', '2026-10-06 13:50:00', 'max-age=3600')",
            (_cached_beef(),),
        ),
        "INSERT INTO kroger_api_usage (api, window_started_at, calls, blocked_until, "
        "last_429_at, probe_backoff_s) VALUES "
        "('products', '2026-10-06 12:00:00', 42, NULL, NULL, NULL), "
        "('locations', '2026-10-06 12:05:00', 3, '2026-10-07 12:05:00', '2026-10-06 12:06:00', "
        "60)",
    ]


# Synthetic rows to insert, per released revision (the tables that exist at that revision).
SEEDS: dict[str, Callable[[], list[Statement]]] = {
    "202610061200": lambda: [
        # updated_at as committed, so a rebuild is byte-identical.
        "UPDATE household SET name = 'Sample household', updated_at = '2026-10-06 21:24:30'",
        "UPDATE app_meta SET auth_epoch = 3, last_boot_version = '0.1.0'",
        *_PEOPLE,
    ],
    "202610062123": _m1,
}


def build(revision: str) -> Path:
    if revision not in SEEDS:
        raise SystemExit(f"add synthetic rows for {revision} to SEEDS first")
    out = HERE / f"{revision}.sql"
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "dinnerbell.db"
        engine = migrate.migration_engine(db)
        try:
            with engine.connect() as conn, conn.begin():
                config = migrate.alembic_config()
                config.attributes["connection"] = conn
                command.upgrade(config, revision)
                for statement in SEEDS[revision]():
                    if isinstance(statement, str):
                        conn.exec_driver_sql(statement)
                    else:
                        conn.exec_driver_sql(*statement)
        finally:
            engine.dispose()
        conn = sqlite3.connect(db)
        try:
            dump = "\n".join(conn.iterdump()) + "\n"
        finally:
            conn.close()
    out.write_text(dump)
    return out


if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(f"wrote {build(name).relative_to(Path.cwd())}")
