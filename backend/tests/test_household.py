from __future__ import annotations

import httpx

from dinnerbell.db.export import EXPORT_EXCLUDED, EXPORT_TABLES
from dinnerbell.db.models import Base
from tests.support import CSRF, login


async def test_members_get_marker_colors_in_order(client: httpx.AsyncClient) -> None:
    await login(client)
    colors: list[str] = []
    for name in ("Mia", "Sample Kid", "Sample Parent"):
        response = await client.post("/api/members", json={"name": name}, headers=CSRF)
        assert response.status_code == 201
        colors.append(response.json()["marker_color"])
    assert colors == ["basil", "tomato", "carrot"]
    listed = (await client.get("/api/members")).json()
    assert [m["name"] for m in listed] == ["Mia", "Sample Kid", "Sample Parent"]


async def test_rename_recolor_archive_and_restore(client: httpx.AsyncClient) -> None:
    await login(client)
    member = (await client.post("/api/members", json={"name": "Mia"}, headers=CSRF)).json()
    renamed = await client.patch(
        f"/api/members/{member['id']}", json={"name": "Mia R", "marker_color": "plum"}, headers=CSRF
    )
    assert renamed.json() == {"id": member["id"], "name": "Mia R", "marker_color": "plum"}
    await client.post(f"/api/members/{member['id']}/archive", headers=CSRF)
    assert (await client.get("/api/members")).json() == []
    await client.post(f"/api/members/{member['id']}/restore", headers=CSRF)
    assert len((await client.get("/api/members")).json()) == 1


async def test_member_names_are_validated(client: httpx.AsyncClient) -> None:
    await login(client)
    response = await client.post("/api/members", json={"name": "   "}, headers=CSRF)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid"


async def test_household_name(client: httpx.AsyncClient) -> None:
    await login(client)
    assert (await client.get("/api/settings")).json() == {"household_name": "Our household"}
    response = await client.patch("/api/settings", json={"household_name": "Home"}, headers=CSRF)
    assert response.json() == {"household_name": "Home"}


async def test_export_contains_household_data_only(client: httpx.AsyncClient) -> None:
    await login(client)
    await client.post("/api/members", json={"name": "Mia"}, headers=CSRF)
    export = (await client.get("/api/export")).json()
    assert export["format"] == "dinner-bell-export"
    assert export["format_version"] == 1
    assert set(export["data"]) == set(EXPORT_TABLES)
    assert export["data"]["members"][0]["name"] == "Mia"


def test_every_table_is_classified_for_export() -> None:
    tables = set(Base.metadata.tables)
    exported, excluded = set(EXPORT_TABLES), set(EXPORT_EXCLUDED)
    assert not exported & excluded
    assert tables == exported | excluded, (
        f"classify these tables in db/export.py: {sorted(tables - exported - excluded)}"
    )


async def test_health_and_version(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/health")).json() == {"status": "ok"}
    version = (await client.get("/api/version")).json()
    assert set(version) == {"version", "revision", "created"}


async def test_diagnostics_show_how_the_client_is_seen(client: httpx.AsyncClient) -> None:
    await login(client)
    diagnostics = (await client.get("/api/admin/diagnostics")).json()
    assert diagnostics["kroger_mode"] == "fake"
    assert diagnostics["client"]["trusted_proxies_configured"] is False
    assert "backups" in diagnostics


async def test_backup_endpoints(client: httpx.AsyncClient) -> None:
    await login(client)
    run = await client.post("/api/admin/backups/run", headers=CSRF)
    assert run.status_code == 200
    name = run.json()["file"]
    listing = (await client.get("/api/admin/backups")).json()
    assert listing["files"][0]["name"] == name
    download = await client.get(f"/api/admin/backups/{name}")
    assert download.status_code == 200
    assert download.content.startswith(b"SQLite format 3")
    assert (await client.get("/api/admin/backups/..%2Fdinnerbell.db")).status_code == 404
