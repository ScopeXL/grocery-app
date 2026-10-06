"""The live Kroger client against a simulated Kroger (docs/PLAN.md §7.2). No real network."""

from __future__ import annotations

import asyncio
import base64
import random
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
from structlog.testing import capture_logs

from dinnerbell.core.clock import FakeClock
from dinnerbell.kroger.client import (
    KrogerAuthError,
    KrogerDailyLimitError,
    KrogerRequestError,
    KrogerUnavailableError,
)
from dinnerbell.kroger.live import BACKOFF_BASE_S, LiveKroger
from dinnerbell.kroger.usage import MemoryUsageStore, UsageGuard

START = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)
PRODUCTS = (
    b'{"data": [{"productId": "0000000000042", "description": "Sample Chunky Salsa", '
    b'"items": [{"size": "16 oz", "soldBy": "UNIT", "price": {"regular": 1.15}}]}]}'
)
LOCATIONS = b'{"data": [{"locationId": "99999001", "chain": "SAMPLE MARKET", "name": "Sample"}]}'
SECRET_TERM = "sample secret recipe"

type Queued = httpx.Response | Exception


class SimulatedKroger:
    def __init__(self) -> None:
        self.token_requests: list[httpx.Request] = []
        self.api_requests: list[httpx.Request] = []
        self.queue: list[Queued] = []
        self.token_status = 200
        self.token_lifetime = 1800
        self.token_delay = 0

    async def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/connect/oauth2/token"):
            self.token_requests.append(request)
            for _ in range(self.token_delay):
                await asyncio.sleep(0)
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_client"})
            return httpx.Response(
                200,
                json={
                    "access_token": f"token-{len(self.token_requests)}",
                    "expires_in": self.token_lifetime,
                    "token_type": "bearer",
                },
                headers={"cache-control": "no-store"},
            )
        self.api_requests.append(request)
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        body = LOCATIONS if request.url.path.endswith("/locations") else PRODUCTS
        return httpx.Response(200, content=body, headers={"cache-control": "max-age=600"})


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(START)


@pytest.fixture
def kroger_site() -> SimulatedKroger:
    return SimulatedKroger()


@pytest.fixture
def delays() -> list[float]:
    return []


@pytest.fixture
def kroger(kroger_site: SimulatedKroger, clock: FakeClock, delays: list[float]) -> LiveKroger:
    async def record_sleep(seconds: float) -> None:
        delays.append(seconds)

    return LiveKroger(
        "sample-client-id",
        "sample-client-secret",
        usage=UsageGuard(MemoryUsageStore(), clock),
        clock=clock,
        transport=httpx.MockTransport(kroger_site.handle),
        base_url="https://api.kroger.test/v1",
        sleep=record_sleep,
        rng=random.Random(7),
    )


def status(code: int, **headers: str) -> httpx.Response:
    return httpx.Response(code, json={"errors": {}}, headers=headers)


async def test_search_sends_the_documented_filters_and_parses_exact_prices(
    kroger: LiveKroger, kroger_site: SimulatedKroger, clock: FakeClock
) -> None:
    found = await kroger.search_products("salsa", "99999001", limit=5)
    (request,) = kroger_site.api_requests
    params = parse_qs(request.url.query.decode())
    assert params == {
        "filter.term": ["salsa"],
        "filter.locationId": ["99999001"],
        "filter.limit": ["5"],
        "filter.start": ["1"],
    }
    assert request.headers["authorization"] == "Bearer token-1"
    assert request.headers["user-agent"].startswith("DinnerBell/")
    (product,) = found.data
    assert product.price is not None and product.price.regular == 115
    assert found.cache.expires_at == clock.now() + timedelta(seconds=600)


async def test_the_token_uses_basic_auth_and_client_credentials(
    kroger: LiveKroger, kroger_site: SimulatedKroger
) -> None:
    await kroger.locations("00001")
    (token_request,) = kroger_site.token_requests
    expected = base64.b64encode(b"sample-client-id:sample-client-secret").decode()
    assert token_request.headers["authorization"] == f"Basic {expected}"
    assert parse_qs(token_request.content.decode()) == {
        "grant_type": ["client_credentials"],
        "scope": ["product.compact"],
    }


async def test_the_token_is_reused_until_a_minute_remains(
    kroger: LiveKroger, kroger_site: SimulatedKroger, clock: FakeClock
) -> None:
    await kroger.search_products("salsa", "99999001")
    clock.advance(seconds=1739)  # 61 s left: still fresh
    await kroger.search_products("salsa", "99999001")
    assert len(kroger_site.token_requests) == 1
    clock.advance(seconds=2)  # 59 s left: refresh first
    await kroger.search_products("salsa", "99999001")
    assert len(kroger_site.token_requests) == 2
    assert kroger_site.api_requests[-1].headers["authorization"] == "Bearer token-2"


async def test_concurrent_requests_share_one_token_fetch(
    kroger: LiveKroger, kroger_site: SimulatedKroger
) -> None:
    kroger_site.token_delay = 5
    await asyncio.gather(*(kroger.search_products("salsa", "99999001") for _ in range(4)))
    assert len(kroger_site.token_requests) == 1
    assert len(kroger_site.api_requests) == 4


async def test_a_401_refreshes_the_token_and_retries_once(
    kroger: LiveKroger, kroger_site: SimulatedKroger
) -> None:
    kroger_site.queue = [status(401)]
    found = await kroger.search_products("salsa", "99999001")
    assert len(found.data) == 1
    assert len(kroger_site.token_requests) == 2
    assert [r.headers["authorization"] for r in kroger_site.api_requests] == [
        "Bearer token-1",
        "Bearer token-2",
    ]


async def test_a_second_401_is_an_auth_error(
    kroger: LiveKroger, kroger_site: SimulatedKroger
) -> None:
    kroger_site.queue = [status(401), status(401)]
    with pytest.raises(KrogerAuthError):
        await kroger.search_products("salsa", "99999001")
    assert len(kroger_site.api_requests) == 2


async def test_server_errors_are_retried_with_full_jitter(
    kroger: LiveKroger, kroger_site: SimulatedKroger, delays: list[float]
) -> None:
    kroger_site.queue = [status(503), status(502)]
    found = await kroger.search_products("salsa", "99999001")
    assert len(found.data) == 1
    assert len(kroger_site.api_requests) == 3
    assert len(delays) == 2
    assert 0 <= delays[0] <= BACKOFF_BASE_S
    assert 0 <= delays[1] <= BACKOFF_BASE_S * 2


async def test_three_server_errors_give_up(
    kroger: LiveKroger, kroger_site: SimulatedKroger, delays: list[float]
) -> None:
    kroger_site.queue = [status(503), status(500), status(504)]
    with pytest.raises(KrogerUnavailableError):
        await kroger.search_products("salsa", "99999001")
    assert len(kroger_site.api_requests) == 3
    assert len(delays) == 2


async def test_retry_after_is_honored_and_long_waits_give_up_at_once(
    kroger: LiveKroger, kroger_site: SimulatedKroger, delays: list[float]
) -> None:
    kroger_site.queue = [status(503, **{"retry-after": "2"})]
    await kroger.search_products("salsa", "99999001")
    assert delays == [2.0]
    kroger_site.queue = [status(503, **{"retry-after": "120"})]
    with pytest.raises(KrogerUnavailableError):
        await kroger.search_products("salsa", "99999001")
    assert delays == [2.0]  # no wait: two minutes is too long to hold a request open


async def test_connection_errors_are_retried(
    kroger: LiveKroger, kroger_site: SimulatedKroger, delays: list[float]
) -> None:
    request = httpx.Request("GET", "https://api.kroger.test/v1/products")
    kroger_site.queue = [httpx.ConnectError("down", request=request)]
    kroger_site.queue.append(httpx.ReadTimeout("slow", request=request))
    found = await kroger.search_products("salsa", "99999001")
    assert len(found.data) == 1
    assert len(delays) == 2


async def test_a_rejected_request_is_not_retried(
    kroger: LiveKroger, kroger_site: SimulatedKroger, delays: list[float]
) -> None:
    kroger_site.queue = [status(400)]
    with pytest.raises(KrogerRequestError) as rejected:
        await kroger.search_products("salsa", "99999001")
    assert rejected.value.status == 400
    assert len(kroger_site.api_requests) == 1
    assert delays == []


async def test_a_429_blocks_that_bucket_without_sending_more(
    kroger: LiveKroger, kroger_site: SimulatedKroger, clock: FakeClock
) -> None:
    kroger_site.queue = [status(429)]
    with pytest.raises(KrogerDailyLimitError) as limit:
        await kroger.search_products("salsa", "99999001")
    assert limit.value.retry_at == clock.now() + timedelta(hours=1)
    with pytest.raises(KrogerDailyLimitError):
        await kroger.get_product("0000000000042", "99999001")
    assert len(kroger_site.api_requests) == 1  # the second call never left
    await kroger.locations("00001")  # another bucket still works
    assert len(kroger_site.api_requests) == 2


async def test_a_refused_secret_is_an_auth_error_and_nothing_else_is_sent(
    kroger: LiveKroger, kroger_site: SimulatedKroger
) -> None:
    kroger_site.token_status = 401
    with pytest.raises(KrogerAuthError):
        await kroger.search_products("salsa", "99999001")
    assert kroger_site.api_requests == []


async def test_a_missing_product_is_none(kroger: LiveKroger, kroger_site: SimulatedKroger) -> None:
    kroger_site.queue = [status(404)]
    found = await kroger.get_product("0000000000099", "99999001")
    assert found.data is None
    assert not found.cache.storable


async def test_batches_hold_one_to_fifty_ids(kroger: LiveKroger) -> None:
    with pytest.raises(ValueError, match="1 to 50"):
        await kroger.get_products([str(n) for n in range(51)], "99999001")
    with pytest.raises(ValueError, match="1 to 50"):
        await kroger.get_products([], "99999001")


async def test_logs_never_contain_the_search_term(
    kroger: LiveKroger, kroger_site: SimulatedKroger
) -> None:
    kroger_site.queue = [status(503), status(503), status(503)]
    with capture_logs() as logs:
        with pytest.raises(KrogerUnavailableError) as failure:
            await kroger.search_products(SECRET_TERM, "99999001")
        await kroger.search_products(SECRET_TERM, "99999001")
    assert logs
    assert "secret recipe" not in str(logs)
    assert "secret recipe" not in str(failure.value)
    assert failure.value.__suppress_context__


def test_the_live_client_refuses_to_run_under_pytest_without_a_transport(
    clock: FakeClock,
) -> None:
    with pytest.raises(RuntimeError, match="KROGER_LIVE"):
        LiveKroger("id", "secret", usage=UsageGuard(MemoryUsageStore(), clock), clock=clock)
