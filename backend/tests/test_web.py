"""Security headers and serving the built SPA."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from dinnerbell.app import create_app
from dinnerbell.web.headers import PAGE_CSP, SERVICE_WORKER_CSP
from tests.support import BASE_URL, make_settings


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><div id=root></div>")
    (root / "assets" / "app-abc123.js").write_text("console.log('hi')")
    (root / "sw.js").write_text("self.addEventListener('install', () => {})")
    (root / "manifest.webmanifest").write_text('{"name": "Dinner Bell"}')
    return root


@pytest.fixture
async def spa_client(data_dir: Path, static_dir: Path) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_settings(data_dir, dinnerbell_static_dir=str(static_dir)))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
            yield client


async def test_security_headers_on_api_responses(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/version")
    assert response.headers["content-security-policy"] == PAGE_CSP
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-store"
    assert int(response.headers["x-server-time-ms"]) > 0
    assert "strict-transport-security" not in response.headers  # http localhost


async def test_hsts_only_over_https(data_dir: Path) -> None:
    app = create_app(make_settings(data_dir, app_base_url="https://dinner.example.test"))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://x.test") as client:
            response = await client.get("/api/version")
    assert response.headers["strict-transport-security"] == "max-age=31536000"


async def test_unknown_api_paths_are_json_404s(spa_client: httpx.AsyncClient) -> None:
    response = await spa_client.get("/api/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_deep_links_get_the_spa_without_caching(spa_client: httpx.AsyncClient) -> None:
    response = await spa_client.get("/plan/this-week")
    assert response.status_code == 200
    assert "id=root" in response.text
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["content-security-policy"] == PAGE_CSP


async def test_hashed_assets_are_immutable(spa_client: httpx.AsyncClient) -> None:
    response = await spa_client.get("/assets/app-abc123.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_missing_assets_are_404_not_index(spa_client: httpx.AsyncClient) -> None:
    response = await spa_client.get("/assets/gone-123.js")
    assert response.status_code == 404
    assert "id=root" not in response.text


async def test_service_worker_gets_its_own_csp(spa_client: httpx.AsyncClient) -> None:
    response = await spa_client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["content-security-policy"] == SERVICE_WORKER_CSP
    assert response.headers["cache-control"] == "no-cache"


async def test_manifest_has_the_right_type(spa_client: httpx.AsyncClient) -> None:
    response = await spa_client.get("/manifest.webmanifest")
    assert response.headers["content-type"].startswith("application/manifest+json")


async def test_path_traversal_falls_back_to_index(spa_client: httpx.AsyncClient) -> None:
    response = await spa_client.get("/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in {200, 404}
    assert "root:" not in response.text
