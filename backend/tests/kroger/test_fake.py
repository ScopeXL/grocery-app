"""The synthetic Kroger used by development, tests, e2e runs and screenshots."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dinnerbell.core.clock import FakeClock
from dinnerbell.kroger.client import KrogerDailyLimitError
from dinnerbell.kroger.fake import FakeKroger, image_svg
from dinnerbell.kroger.parse import SoldBy

STORE = "99999001"


@pytest.fixture
def kroger() -> FakeKroger:
    return FakeKroger(FakeClock(datetime(2026, 10, 6, 14, 0, tzinfo=UTC)))


async def test_search_matches_every_word_in_any_order(kroger: FakeKroger) -> None:
    cheese = await kroger.search_products("cheese", STORE)
    assert [p.description for p in cheese.data] == [
        "Sample Shredded Cheddar Cheese",
        "Sample Aged Gouda Cheese",
    ]
    assert [p.description for p in (await kroger.search_products("CHEDDAR shredded", STORE)).data]
    assert (await kroger.search_products("xyz", STORE)).data == ()
    assert (await kroger.search_products("   ", STORE)).data == ()
    assert cheese.cache.storable


async def test_search_pages_with_limit_and_start(kroger: FakeKroger) -> None:
    every = (await kroger.search_products("sample", STORE, limit=50)).data
    page = (await kroger.search_products("sample", STORE, limit=3, start=4)).data
    assert page == every[3:6]


async def test_the_fixtures_cover_the_awkward_cases(kroger: FakeKroger) -> None:
    every = (await kroger.search_products("sample", STORE, limit=50)).data
    by_id = {product.product_id: product for product in every}
    assert by_id["0000000000004"].sold_by is SoldBy.WEIGHT  # "weight", lowercase
    assert by_id["0000000000003"].sold_by is SoldBy.UNIT  # "Unit"
    assert by_id["0000000000002"].price and by_id["0000000000002"].price.promo is None
    assert by_id["0000000000016"].size == "Varies"  # an unreadable size
    assert by_id["0000000000017"].stock_level == "LOW"
    assert by_id["0000000000018"].price is None  # not sold at this store
    assert by_id["0000000000019"].image is None  # no photo at all
    assert by_id["0000000000009"].aisle is None  # a placeholder aisle


async def test_an_unknown_store_gets_no_prices_or_aisles(kroger: FakeKroger) -> None:
    (milk,) = (await kroger.search_products("whole milk", "12345678")).data
    assert (milk.price, milk.aisles, milk.stock_level) == (None, (), None)


async def test_products_by_id_and_by_upc(kroger: FakeKroger) -> None:
    one = await kroger.get_product("0000000000001", STORE)
    assert one.data is not None and one.data.description == "Sample Whole Milk"
    assert (await kroger.get_product("0000000009999", STORE)).data is None
    batch = await kroger.get_products(["0000000000001", "0000000000005", "nope"], STORE)
    assert [p.product_id for p in batch.data] == ["0000000000001", "0000000000005"]


async def test_locations_include_a_fuel_center_and_a_zip_with_none(kroger: FakeKroger) -> None:
    stores = (await kroger.locations("00001")).data
    assert [store.is_fuel_center for store in stores] == [False, True, False]
    assert (await kroger.locations("00000")).data == ()
    assert [chain.domain for chain in (await kroger.chains()).data] == ["example.com", None]


async def test_the_magic_term_simulates_the_daily_limit(kroger: FakeKroger) -> None:
    with pytest.raises(KrogerDailyLimitError):
        await kroger.search_products("dailylimit", STORE)


def test_placeholder_photos_exist_only_for_fixture_products() -> None:
    svg = image_svg("0000000000001.svg")
    assert svg is not None and svg.startswith("<svg") and "Sample Whole Milk" in svg
    assert image_svg("0000000009999.svg") is None
