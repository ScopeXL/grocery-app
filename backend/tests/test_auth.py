from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from dinnerbell.app import create_app
from dinnerbell.core.clock import FakeClock
from dinnerbell.state import AppState
from tests.support import CSRF, PASSWORD, login, make_settings


def state_of(app: FastAPI) -> AppState:
    return app.state.dinnerbell


async def test_login_sets_a_long_lived_http_only_cookie(client: httpx.AsyncClient) -> None:
    response = await login(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("dinnerbell=v1.")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=31536000" in cookie
    body = response.json()
    assert body["member"] is None
    assert body["household_name"] == "Our household"


async def test_https_uses_a_secure_host_cookie(tmp_path: Path, data_dir: Path) -> None:
    settings = make_settings(data_dir, app_base_url="https://dinner.example.test")
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://dinner.example.test"
        ) as client:
            response = await client.post(
                "/api/auth/login", json={"password": PASSWORD}, headers=CSRF
            )
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-dinnerbell=")
    assert "Secure" in cookie
    assert "Path=/" in cookie


async def test_wrong_password_says_exactly_what_happened(client: httpx.AsyncClient) -> None:
    response = await login(client, "not the password")
    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "wrong_password",
        "message": "That password didn't match. Try again.",
    }


async def test_five_failures_lock_out_that_address(client: httpx.AsyncClient) -> None:
    for _ in range(5):
        assert (await login(client, "wrong")).status_code == 401
    blocked = await login(client)  # even the right password waits
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert "Too many tries" in blocked.json()["error"]["message"]


async def test_lockout_expires(client: httpx.AsyncClient, clock: FakeClock) -> None:
    for _ in range(5):
        await login(client, "wrong")
    clock.advance(minutes=16)
    assert (await login(client)).status_code == 200


async def test_protected_routes_need_a_session(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/auth/session")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "signed_out"


async def test_mutations_need_the_csrf_header(client: httpx.AsyncClient) -> None:
    await login(client)
    no_header = await client.post("/api/members", json={"name": "Mia"})
    assert no_header.status_code == 403
    bad_origin = await client.post(
        "/api/members", json={"name": "Mia"}, headers=CSRF | {"origin": "https://evil.test"}
    )
    assert bad_origin.status_code == 403
    null_origin = await client.post(
        "/api/members", json={"name": "Mia"}, headers=CSRF | {"origin": "null"}
    )
    assert null_origin.status_code == 403
    ok = await client.post("/api/members", json={"name": "Mia"}, headers=CSRF)
    assert ok.status_code == 201


async def test_choosing_who_is_using_this_device(client: httpx.AsyncClient) -> None:
    await login(client)
    member = (await client.post("/api/members", json={"name": "Mia"}, headers=CSRF)).json()
    chosen = await client.put("/api/auth/member", json={"member_id": member["id"]}, headers=CSRF)
    assert chosen.json()["member"]["name"] == "Mia"
    session = (await client.get("/api/auth/session")).json()
    assert session["member"]["id"] == member["id"]
    cleared = await client.put("/api/auth/member", json={"member_id": None}, headers=CSRF)
    assert cleared.json()["member"] is None


async def test_choosing_an_unknown_member_is_refused(client: httpx.AsyncClient) -> None:
    await login(client)
    response = await client.put("/api/auth/member", json={"member_id": "nope"}, headers=CSRF)
    assert response.status_code == 404


@pytest.fixture
async def second_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8080") as http:
        yield http


async def test_sign_out_other_devices(
    client: httpx.AsyncClient, second_client: httpx.AsyncClient
) -> None:
    await login(client)
    await login(second_client)
    devices = (await client.get("/api/auth/devices")).json()
    assert len(devices) == 2
    assert sum(d["is_current"] for d in devices) == 1
    response = await client.post("/api/auth/devices/sign-out-others", headers=CSRF)
    assert response.status_code == 204
    assert (await second_client.get("/api/auth/session")).status_code == 401
    assert (await client.get("/api/auth/session")).status_code == 200


async def test_logout_revokes_this_device(client: httpx.AsyncClient) -> None:
    await login(client)
    old_cookie = client.cookies.get("dinnerbell")
    assert (await client.post("/api/auth/logout", headers=CSRF)).status_code == 204
    client.cookies.set("dinnerbell", old_cookie or "")
    assert (await client.get("/api/auth/session")).status_code == 401


async def test_cookie_is_renewed_after_30_days(client: httpx.AsyncClient, clock: FakeClock) -> None:
    await login(client)
    clock.advance(days=31)
    response = await client.get("/api/auth/session")
    assert response.status_code == 200
    assert "dinnerbell=v1." in response.headers.get("set-cookie", "")


async def test_epoch_change_signs_everyone_out(app: FastAPI, client: httpx.AsyncClient) -> None:
    await login(client)
    state_of(app).auth.epoch += 1
    assert (await client.get("/api/auth/session")).status_code == 401


async def test_tampered_cookie_is_rejected(client: httpx.AsyncClient) -> None:
    await login(client)
    value = client.cookies.get("dinnerbell") or ""
    client.cookies.set("dinnerbell", value[:-2] + "xx")
    assert (await client.get("/api/auth/session")).status_code == 401


def test_device_labels() -> None:
    from dinnerbell.auth.password import device_label

    iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Version/18.0 Safari/604.1"
    android = "Mozilla/5.0 (Linux; Android 15; Pixel 8) Chrome/130.0 Mobile Safari/537.36"
    assert device_label(iphone) == "iPhone, Safari"
    assert device_label(android) == "Android phone, Chrome"
    assert device_label(None) == "Device"
