"""Imports every model so Base.metadata is complete (Alembic, export and tests rely on it).

Add each new feature's models module here.
"""

from __future__ import annotations

from dinnerbell.auth import models as auth_models
from dinnerbell.catalog import models as catalog_models
from dinnerbell.db.base import Base
from dinnerbell.household import models as household_models
from dinnerbell.kroger import models as kroger_models
from dinnerbell.meals import models as meals_models
from dinnerbell.planning import models as planning_models
from dinnerbell.shopping import models as shopping_models
from dinnerbell.stores import models as stores_models

__all__ = [
    "Base",
    "auth_models",
    "catalog_models",
    "household_models",
    "kroger_models",
    "meals_models",
    "planning_models",
    "shopping_models",
    "stores_models",
]
