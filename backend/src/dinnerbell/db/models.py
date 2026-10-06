"""Imports every model so Base.metadata is complete (Alembic, export and tests rely on it).

Add each new feature's models module here.
"""

from __future__ import annotations

from dinnerbell.auth import models as auth_models
from dinnerbell.db.base import Base
from dinnerbell.household import models as household_models

__all__ = ["Base", "auth_models", "household_models"]
