"""Finding and choosing the household's store, and seeding its sections (docs/PLAN.md §7.3)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dinnerbell.core.errors import AppError
from dinnerbell.household.service import household
from dinnerbell.kroger.client import KrogerApi
from dinnerbell.kroger.parse import Location
from dinnerbell.stores.models import Store, StoreSection
from dinnerbell.stores.schemas import StoreOption, StoreOut

SEARCH_LIMIT = 20

# The default walk: Produce first, then Bakery and Deli, the aisles in ascending order (sort
# indexes 1000 + the aisle number, created when an aisle first appears), then Meat & Seafood,
# Dairy and Frozen last, and anything unplaced at the very end.
DEFAULT_SECTIONS: tuple[tuple[str, str, int], ...] = (
    ("cat:produce", "Produce", 100),
    ("cat:bakery", "Bakery", 200),
    ("cat:deli", "Deli", 300),
    ("cat:meat-seafood", "Meat & Seafood", 9000),
    ("cat:dairy", "Dairy", 9100),
    ("cat:frozen", "Frozen", 9200),
    ("cat:other", "Other", 9900),
)


async def search(kroger: KrogerApi, zip_code: str) -> list[StoreOption]:
    found = await kroger.locations(zip_code, limit=SEARCH_LIMIT)
    return [
        StoreOption(location_id=s.location_id, name=_name(s), address_lines=_address(s))
        for s in found.data
        if not s.is_fuel_center
    ]


async def fetch_location(kroger: KrogerApi, location_id: str) -> tuple[Location, str | None]:
    """The store's details and its chain's web domain, before any write transaction opens."""
    found = (await kroger.location(location_id)).data
    if found is None or found.is_fuel_center:
        raise AppError(404, "store_not_found", "That store couldn't be found. Search again.")
    chains = (await kroger.chains()).data
    domain = next((c.domain for c in chains if c.name.upper() == found.chain.upper()), None)
    return found, domain


async def choose(session: AsyncSession, location: Location, chain_domain: str | None) -> Store:
    store = await session.scalar(select(Store).where(Store.location_id == location.location_id))
    if store is None:
        store = Store(location_id=location.location_id)
        session.add(store)
    store.chain = location.chain
    store.name = _name(location)
    store.address_line1 = location.address_line1
    store.address_line2 = location.address_line2
    store.city = location.city
    store.state = location.state
    store.zip_code = location.zip_code
    store.timezone = location.timezone
    store.chain_domain = chain_domain
    store.departments = list(location.departments)
    await session.flush()
    await seed_sections(session, store)
    (await household(session)).active_store_id = store.id
    return store


async def seed_sections(session: AsyncSession, store: Store) -> None:
    existing = set(
        await session.scalars(select(StoreSection.key).where(StoreSection.store_id == store.id))
    )
    for key, label, sort_index in DEFAULT_SECTIONS:
        if key not in existing:
            session.add(
                StoreSection(store_id=store.id, key=key, label=label, sort_index=sort_index)
            )


async def active_store(session: AsyncSession) -> Store | None:
    store_id = (await household(session)).active_store_id
    return await session.get(Store, store_id) if store_id else None


def store_out(store: Store) -> StoreOut:
    lines = [
        line
        for line in (
            store.address_line1,
            store.address_line2,
            _city_line(store.city, store.state, store.zip_code),
        )
        if line
    ]
    return StoreOut(name=store.name, address_lines=lines)


def _name(location: Location) -> str:
    """Kroger's names arrive in assorted casing ("KROGER - MAIN ST"); keep them as sent."""
    return re.sub(r"\s+", " ", location.name).strip() or location.chain


def _address(location: Location) -> list[str]:
    city = _city_line(location.city, location.state, location.zip_code)
    return [line for line in (location.address_line1, location.address_line2, city) if line]


def _city_line(city: str | None, state: str | None, zip_code: str | None) -> str | None:
    place = ", ".join(part for part in (city, state) if part)
    text = " ".join(part for part in (place, zip_code) if part)
    return text or None
