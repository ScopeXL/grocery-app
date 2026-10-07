"""Product search, the household's Kroger account (Connect Kroger), and sample mode's stand-ins
for Kroger's photos and sign-in page."""

from __future__ import annotations

from html import escape
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from dinnerbell.auth.deps import SessionDep, read_token
from dinnerbell.catalog import service
from dinnerbell.catalog.schemas import ProductResult
from dinnerbell.core.config import KROGER_CALLBACK_PATH, KrogerMode
from dinnerbell.core.errors import AppError
from dinnerbell.core.logging import get_logger
from dinnerbell.household.models import Member
from dinnerbell.kroger.account import ConnectResult
from dinnerbell.kroger.fake import FakeKroger, image_svg
from dinnerbell.kroger.models import KrogerToken
from dinnerbell.kroger.schemas import ConnectOut, KrogerAccountOut
from dinnerbell.state import AppState, StateDep

router = APIRouter(prefix="/api/kroger", tags=["kroger"])
fake_routes = APIRouter(prefix="/api/kroger", include_in_schema=False)
log = get_logger(__name__)

OAuthState = Annotated[str | None, Query(alias="state", max_length=200)]


@router.get("/products")
async def search_products(
    state: StateDep, session: SessionDep, q: Annotated[str, Query(max_length=100)]
) -> list[ProductResult]:
    """Search terms are never stored or logged (ADR 0016)."""
    return await service.search_products(state, q)


# ---- the household's Kroger account ----------------------------------------------------------


@router.get("/account")
async def kroger_account(state: StateDep, session: SessionDep) -> KrogerAccountOut:
    async with state.db.read() as db:
        row = await db.get(KrogerToken, 1)
        member_id = row.connected_by_member_id if row else None
        member = await db.get(Member, member_id) if member_id else None
    status = row.status if row else "disconnected"
    return KrogerAccountOut(
        status="connected"
        if status == "connected"
        else "needs_reconnect"
        if status == "needs_reconnect"
        else "disconnected",
        connected_by=member.name if member and status == "connected" else None,
        connected_at=row.connected_at if row and status == "connected" else None,
        can_connect=state.account.can_connect,
        demo=state.settings.kroger_mode is KrogerMode.FAKE,
    )


@router.post("/connect")
async def connect(state: StateDep, session: SessionDep) -> ConnectOut:
    """Start Connect Kroger: the phone goes to the URL, signs in, and comes back to the callback."""
    if not state.account.can_connect:
        raise AppError(
            409,
            "kroger_connect_unavailable",
            "Connecting a Kroger account isn't set up on this server yet. Whoever runs Dinner "
            "Bell can add KROGER_REDIRECT_URI.",
        )
    started = await state.account.start(session.device_id)
    return ConnectOut(authorize_url=started.authorize_url)


@router.get("/callback", include_in_schema=False)
async def callback(
    request: Request,
    state: StateDep,
    oauth_state: OAuthState = None,
    code: Annotated[str | None, Query(max_length=2000)] = None,
    error: Annotated[str | None, Query(max_length=100)] = None,
) -> RedirectResponse:
    """Where Kroger sends the phone back. The state is the proof: it is marked used before
    anything else, and the session is optional, because an iPhone can finish the sign-in in
    another browser. A session that is there must be the device that started (PLAN §7.5)."""
    token = read_token(request, state)
    result = await _finish_connect(
        state, token.device_id if token else None, oauth_state, code, error
    )
    log.info("kroger.callback", result=result.value, signed_in=token is not None)
    target = f"/settings?kroger={result.value}" if token else f"/kroger-done?result={result.value}"
    return RedirectResponse(target, status_code=303)


async def _finish_connect(
    state: AppState,
    device_id: str | None,
    oauth_state: str | None,
    code: str | None,
    error: str | None,
) -> ConnectResult:
    if not oauth_state or not state.account.can_connect:
        return ConnectResult.EXPIRED
    claimed = await state.account.claim(oauth_state)
    if claimed is None:
        return ConnectResult.EXPIRED
    verifier, started_by = claimed
    if device_id is not None and device_id != started_by:
        return ConnectResult.FAILED
    if started_by not in state.auth.known_devices or started_by in state.auth.revoked_devices:
        return ConnectResult.FAILED
    if error is not None:
        return ConnectResult.DENIED if error == "access_denied" else ConnectResult.FAILED
    if not code:
        return ConnectResult.FAILED
    return await state.account.finish(code, verifier, started_by)


@router.delete("/connection", status_code=204)
async def disconnect(state: StateDep, session: SessionDep) -> None:
    await state.account.disconnect()


# ---- sample mode ---------------------------------------------------------------------------------


@fake_routes.get("/fake-images/{name}")
async def fake_image(name: str) -> Response:
    svg = image_svg(name)
    if svg is None:
        raise AppError(404, "not_found", "That photo couldn't be found.")
    return Response(
        svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@fake_routes.get("/fake-authorize")
async def fake_authorize(
    state: StateDep,
    oauth_state: OAuthState = None,
    code_challenge: Annotated[str, Query(max_length=128)] = "",
) -> HTMLResponse:
    """Stands in for Kroger's sign-in page in sample mode. It always returns to this server's
    callback, whatever it's asked, so it can't be used to send anyone elsewhere."""
    fake = state.kroger
    if not isinstance(fake, FakeKroger) or not oauth_state or not code_challenge:
        raise AppError(404, "not_found", "That page couldn't be found.")
    allow = urlencode({"code": fake.issue_code(code_challenge), "state": oauth_state})
    deny = urlencode({"error": "access_denied", "state": oauth_state})
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo sign-in</title>
</head>
<body>
<main>
<h1>Demo sign-in</h1>
<p>Dinner Bell is running with sample data, so this page stands in for signing in to your
Kroger account. Nothing real is connected, and nothing goes to a real cart.</p>
<p><a href="{escape(KROGER_CALLBACK_PATH + "?" + allow)}">Allow</a></p>
<p><a href="{escape(KROGER_CALLBACK_PATH + "?" + deny)}">Don't allow</a></p>
</main>
</body>
</html>
"""
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})
