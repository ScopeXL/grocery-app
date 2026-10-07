"""Export all household data as JSON (docs/PLAN.md §11.6).

Every table must be listed in exactly one of EXPORT_TABLES or EXPORT_EXCLUDED; a test fails
otherwise, which forces a decision whenever a table is added.
"""

from __future__ import annotations

import base64
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.db.models import Base

EXPORT_TABLES: tuple[str, ...] = (
    "household",
    "members",
    "stores",
    "store_sections",
    "items",
    "photos",
    "dishes",
    "dish_items",
    "dish_pairings",
    "plans",
    "plan_meals",
    "plan_meal_sides",
    "plan_extras",
    "plan_item_overrides",
)
# Not household data: secrets and sessions, or Kroger's data, which may only be cached (ADR 0016).
EXPORT_EXCLUDED: tuple[str, ...] = (
    "app_meta",
    "devices",
    "kroger_product_cache",
    "kroger_api_usage",
)
FORMAT = "dinner-bell-export"
FORMAT_VERSION = 1


def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Fraction | Decimal):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode()
    return value


async def export_data(
    session: AsyncSession, *, app_version: str, schema_revision: str | None, exported_at: datetime
) -> dict[str, Any]:
    data: dict[str, list[dict[str, Any]]] = {}
    for name in EXPORT_TABLES:
        table = Base.metadata.tables[name]
        rows = await session.execute(select(table))
        data[name] = [{key: _plain(value) for key, value in row.items()} for row in rows.mappings()]
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "app_version": app_version,
        "schema_revision": schema_revision,
        "exported_at": exported_at.isoformat(),
        "data": data,
    }
