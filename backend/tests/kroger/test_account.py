"""Connect Kroger, its tokens and Disconnect (PLAN §7.5, §10.7), through the demo sign-in page.

Sample mode checks what Kroger would: single-use codes and refresh tokens, the PKCE verifier,
and access tokens that last 30 minutes. The fake clock starts at 2026-10-06T14:00Z.
"""

from __future__ import annotations

import asyncio
import html
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from structlog.testing import capture_logs

from dinnerbell.core.clock import FakeClock
from dinnerbell.core.crypto import token_cipher
from dinnerbell.kroger.account import AccountStatus, KrogerAccount, KrogerNotConnectedError
from dinnerbell.kroger.client import KrogerGrantError, KrogerUnavailableError, TokenGrant
from dinnerbell.kroger.fake import FakeKroger
from dinnerbell.kroger.models import KrogerOAuthState, KrogerToken
from dinnerbell.state import AppState
from tests.support import BASE_URL, CSRF, SECRET, login


def app_state(app: FastAPI) -> AppState:
    return app.state.dinnerbell


def fake(app: FastAPI) -> FakeKroger:
    kroger = app_state(app).kroger
    assert isinstance(kroger, FakeKroger)
    return kroger


async def token_row(app: FastAPI) -> KrogerToken:
    async with app_state(app).db.read() as db:
        row = await db.get(KrogerToken, 1)
    assert row is not None
    return row


async def sign_in_page(client: httpx.AsyncClient) -> str:
    started = await client.post("/api/kroger/connect", headers=CSRF)
    assert started.status_code == 200, started.text
    url = started.json()["authorize_url"]
    assert url.startswith("/api/kroger/fake-authorize?")
    page = await client.get(url)
    assert page.status_code == 200
    assert "Demo sign-in" in page.text
    return page.text


def link(page: str, label: str) -> str:
    found = re.search(rf'href="([^"]+)">{label}<', page)
    assert found, f"no {label} link"
    return html.unescape(found.group(1))


async def connect(client: httpx.AsyncClient) -> str:
    """Connect Kroger and tap Allow. Returns where the callback sent the phone."""
    response = await client.get(link(await sign_in_page(client), "Allow"))
    assert response.status_code == 303
    return response.headers["location"]


@pytest.fixture
async def phone(client: httpx.AsyncClient) -> httpx.AsyncClient:
    await login(client)
    member = (
        await client.post("/api/members", json={"name": "Sample Parent"}, headers=CSRF)
    ).json()
    await client.put("/api/auth/member", json={"member_id": member["id"]}, headers=CSRF)
    return client


@pytest.fixture
async def other_browser(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Another cookie jar, like an iPhone finishing the sign-in outside the installed app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http:
        yield http


@pytest.fixture
def events(app: FastAPI) -> list[tuple[str, dict[str, Any]]]:
    state = app_state(app)
    seen: list[tuple[str, dict[str, Any]]] = []
    original = state.db.publisher

    def record(event_type: str, payload: dict[str, Any]) -> None:
        seen.append((event_type, payload))
        if original is not None:
            original(event_type, payload)

    state.db.publisher = record
    return seen


# ---- connecting -------------------------------------------------------------------------------


async def test_connect_stores_the_tokens_encrypted(
    phone: httpx.AsyncClient, app: FastAPI, events: list[tuple[str, dict[str, Any]]]
) -> None:
    before = (await phone.get("/api/kroger/account")).json()
    assert before == {
        "status": "disconnected",
        "connected_by": None,
        "connected_at": None,
        "can_connect": True,
        "demo": True,
    }
    assert await connect(phone) == "/settings?kroger=connected"
    account = (await phone.get("/api/kroger/account")).json()
    assert (account["status"], account["connected_by"]) == ("connected", "Sample Parent")
    assert account["connected_at"].startswith("2026-10-06T14:00")

    row = await token_row(app)
    assert row.access_enc and row.refresh_enc
    cipher = token_cipher(SECRET)
    access = cipher.decrypt(row.access_enc.encode()).decode()
    assert access.startswith("demo-access.") and access not in row.access_enc
    assert cipher.decrypt(row.refresh_enc.encode()).decode().startswith("demo-refresh.")
    assert (row.scope, row.version) == ("cart.basic:write", 1)
    assert ("settings.changed", {}) in events


async def test_a_sign_in_link_works_once(phone: httpx.AsyncClient) -> None:
    allow = link(await sign_in_page(phone), "Allow")
    first = await phone.get(allow)
    again = await phone.get(allow)
    assert first.headers["location"] == "/settings?kroger=connected"
    assert again.headers["location"] == "/settings?kroger=expired"


async def test_a_sign_in_link_lasts_ten_minutes(phone: httpx.AsyncClient, clock: FakeClock) -> None:
    allow = link(await sign_in_page(phone), "Allow")
    clock.advance(minutes=10, seconds=1)
    response = await phone.get(allow)
    assert response.headers["location"] == "/settings?kroger=expired"
    assert (await phone.get("/api/kroger/account")).json()["status"] == "disconnected"


async def test_finishing_in_another_browser_still_connects(
    phone: httpx.AsyncClient, other_browser: httpx.AsyncClient
) -> None:
    """iOS can finish the sign-in in a different cookie jar: the state is the proof."""
    allow = link(await sign_in_page(phone), "Allow")
    response = await other_browser.get(allow)
    assert response.headers["location"] == "/kroger-done?result=connected"
    assert (await phone.get("/api/kroger/account")).json()["status"] == "connected"


async def test_another_signed_in_device_cant_finish_it(
    phone: httpx.AsyncClient, other_browser: httpx.AsyncClient
) -> None:
    allow = link(await sign_in_page(phone), "Allow")
    await login(other_browser)
    response = await other_browser.get(allow)
    assert response.headers["location"] == "/settings?kroger=failed"
    # The state was spent first, so the right phone can't use it now either.
    assert (await phone.get(allow)).headers["location"] == "/settings?kroger=expired"
    assert (await phone.get("/api/kroger/account")).json()["status"] == "disconnected"


async def test_a_signed_out_device_cant_finish_it(
    phone: httpx.AsyncClient, other_browser: httpx.AsyncClient
) -> None:
    allow = link(await sign_in_page(phone), "Allow")
    await phone.post("/api/auth/logout", headers=CSRF)
    response = await other_browser.get(allow)
    assert response.headers["location"] == "/kroger-done?result=failed"


async def test_dont_allow_leaves_it_disconnected(phone: httpx.AsyncClient) -> None:
    response = await phone.get(link(await sign_in_page(phone), "Don't allow"))
    assert response.headers["location"] == "/settings?kroger=denied"
    assert (await phone.get("/api/kroger/account")).json()["status"] == "disconnected"


async def test_a_code_needs_the_matching_verifier(phone: httpx.AsyncClient, app: FastAPI) -> None:
    """PKCE: a code issued for another sign-in's challenge doesn't work with this state."""
    page = await sign_in_page(phone)
    state = re.search(r"state=([^&\"]+)", html.unescape(link(page, "Allow")))
    assert state
    stolen = fake(app).issue_code("some-other-challenge")
    response = await phone.get(
        "/api/kroger/callback", params={"code": stolen, "state": state.group(1)}
    )
    assert response.headers["location"] == "/settings?kroger=failed"


async def test_a_callback_without_a_state_is_refused(phone: httpx.AsyncClient) -> None:
    response = await phone.get("/api/kroger/callback", params={"code": "demo.x.y"})
    assert response.headers["location"] == "/settings?kroger=expired"


async def test_connect_needs_a_redirect_uri_outside_sample_mode(
    phone: httpx.AsyncClient, app: FastAPI
) -> None:
    state = app_state(app)
    state.account = KrogerAccount(state.kroger, state.db, state.clock, token_cipher(SECRET), None)
    response = await phone.post("/api/kroger/connect", headers=CSRF)
    assert response.status_code == 409
    assert "KROGER_REDIRECT_URI" in response.json()["error"]["message"]
    assert (await phone.get("/api/kroger/account")).json()["can_connect"] is False


async def test_connect_and_disconnect_need_a_signed_in_phone(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/kroger/connect", headers=CSRF)).status_code == 401
    assert (await client.delete("/api/kroger/connection", headers=CSRF)).status_code == 401
    assert (await client.get("/api/kroger/account")).status_code == 401


async def test_disconnect_forgets_tokens_and_sign_ins_in_progress(
    phone: httpx.AsyncClient, app: FastAPI
) -> None:
    await connect(phone)
    pending = link(await sign_in_page(phone), "Allow")
    response = await phone.delete("/api/kroger/connection", headers=CSRF)
    assert response.status_code == 204
    row = await token_row(app)
    assert (row.status, row.access_enc, row.refresh_enc, row.connected_by_member_id) == (
        "disconnected",
        None,
        None,
        None,
    )
    async with app_state(app).db.read() as db:
        assert await db.scalar(select(func.count()).select_from(KrogerOAuthState)) == 0
    assert (await phone.get(pending)).headers["location"] == "/settings?kroger=expired"


async def test_the_sign_in_page_exists_only_in_sample_mode(phone: httpx.AsyncClient) -> None:
    response = await phone.get("/api/kroger/fake-authorize")
    assert response.status_code == 404


# ---- using the account: refreshing ------------------------------------------------------------


async def test_a_fresh_access_token_is_used_as_is(phone: httpx.AsyncClient, app: FastAPI) -> None:
    await connect(phone)
    row = await token_row(app)
    token = await app_state(app).account.access_token()
    assert token == token_cipher(SECRET).decrypt((row.access_enc or "").encode()).decode()
    assert (await token_row(app)).version == row.version


async def test_a_nearly_expired_token_is_refreshed_and_rotated(
    phone: httpx.AsyncClient, app: FastAPI, clock: FakeClock
) -> None:
    await connect(phone)
    before = await token_row(app)
    clock.advance(minutes=26)  # under 5 minutes left of 30
    with capture_logs() as logs:
        token = await app_state(app).account.access_token()
    after = await token_row(app)
    assert token.startswith("demo-access.")
    assert after.refresh_enc != before.refresh_enc
    assert after.refresh_obtained_at == clock.now()
    assert after.version == before.version + 1
    refreshed = [entry for entry in logs if entry["event"] == "kroger.refresh"]
    assert refreshed == [
        {"event": "kroger.refresh", "token_age_h": 0.4, "rotated": True, "log_level": "info"}
    ]


async def test_refreshing_is_single_flight(
    phone: httpx.AsyncClient, app: FastAPI, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    await connect(phone)
    clock.advance(minutes=26)
    kroger = fake(app)
    original = kroger.refresh
    calls: list[str] = []

    async def slow_refresh(refresh_token: str) -> TokenGrant:
        calls.append(refresh_token)
        await asyncio.sleep(0.01)
        return await original(refresh_token)

    monkeypatch.setattr(kroger, "refresh", slow_refresh)
    account = app_state(app).account
    tokens = await asyncio.gather(*(account.access_token() for _ in range(5)))
    assert len(calls) == 1
    assert len(set(tokens)) == 1


async def test_a_refresh_without_a_new_refresh_token_keeps_the_old_one(
    phone: httpx.AsyncClient, app: FastAPI, clock: FakeClock
) -> None:
    await connect(phone)
    before = await token_row(app)
    fake(app).rotate_refresh = False
    clock.advance(minutes=26)
    with capture_logs() as logs:
        await app_state(app).account.access_token()
    after = await token_row(app)
    assert after.refresh_enc == before.refresh_enc
    assert after.refresh_obtained_at == before.refresh_obtained_at
    assert after.access_enc != before.access_enc
    assert "kroger.refresh_not_rotated" in [entry["event"] for entry in logs]


async def test_invalid_grant_asks_the_household_to_reconnect(
    phone: httpx.AsyncClient,
    app: FastAPI,
    clock: FakeClock,
    events: list[tuple[str, dict[str, Any]]],
) -> None:
    await connect(phone)
    events.clear()
    fake(app).refresh_failure = KrogerGrantError("expired")
    clock.advance(minutes=31)
    with pytest.raises(KrogerNotConnectedError) as caught:
        await app_state(app).account.access_token()
    assert caught.value.status is AccountStatus.NEEDS_RECONNECT
    row = await token_row(app)
    assert (row.status, row.access_enc, row.refresh_enc) == ("needs_reconnect", None, None)
    assert events == [("settings.changed", {})]
    assert (await phone.get("/api/kroger/account")).json()["status"] == "needs_reconnect"
    # Connecting again fixes it.
    assert await connect(phone) == "/settings?kroger=connected"
    assert (await token_row(app)).status == "connected"


async def test_an_unclear_refresh_failure_keeps_the_tokens_and_waits(
    phone: httpx.AsyncClient, app: FastAPI, clock: FakeClock
) -> None:
    await connect(phone)
    before = await token_row(app)
    kroger = fake(app)
    kroger.refresh_failure = KrogerUnavailableError("no answer")
    clock.advance(minutes=26)
    account = app_state(app).account
    with pytest.raises(KrogerUnavailableError):
        await account.access_token()
    assert (await token_row(app)).refresh_enc == before.refresh_enc
    with pytest.raises(KrogerUnavailableError):
        await account.access_token()  # backing off: Kroger isn't asked again yet
    clock.advance(minutes=1)
    assert (await account.access_token()).startswith("demo-access.")
    assert (await token_row(app)).status == "connected"


async def test_a_disconnect_during_a_refresh_wins(
    phone: httpx.AsyncClient, app: FastAPI, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    await connect(phone)
    clock.advance(minutes=26)
    kroger = fake(app)
    original = kroger.refresh
    answering = asyncio.Event()
    release = asyncio.Event()

    async def slow_refresh(refresh_token: str) -> TokenGrant:
        answering.set()
        await release.wait()
        return await original(refresh_token)

    monkeypatch.setattr(kroger, "refresh", slow_refresh)
    account = app_state(app).account
    refreshing = asyncio.create_task(account.access_token())
    await answering.wait()
    await account.disconnect()
    release.set()
    with pytest.raises(KrogerNotConnectedError) as caught:
        await refreshing
    assert caught.value.status is AccountStatus.DISCONNECTED
    row = await token_row(app)
    assert (row.status, row.access_enc, row.refresh_enc) == ("disconnected", None, None)


async def test_no_account_means_not_connected(phone: httpx.AsyncClient, app: FastAPI) -> None:
    with pytest.raises(KrogerNotConnectedError) as caught:
        await app_state(app).account.access_token()
    assert caught.value.status is AccountStatus.DISCONNECTED


async def test_tokens_codes_and_states_never_reach_the_logs(
    phone: httpx.AsyncClient, app: FastAPI, clock: FakeClock
) -> None:
    with capture_logs() as logs:
        page = await sign_in_page(phone)
        allow = link(page, "Allow")
        await phone.get(allow)
        clock.advance(minutes=26)
        token = await app_state(app).account.access_token()
    secrets_seen = [token, *re.findall(r"(?:code|state)=([^&]+)", allow)]
    text = repr(logs)
    for value in secrets_seen:
        assert value not in text
    assert "kroger.connected" in [entry["event"] for entry in logs]
