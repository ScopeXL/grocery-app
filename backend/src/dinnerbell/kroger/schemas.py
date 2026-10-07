"""The household's Kroger account as the API sends it (PLAN §7.5, UX §4.16)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AccountStatusName = Literal["disconnected", "connected", "needs_reconnect"]


class KrogerAccountOut(BaseModel):
    status: AccountStatusName
    connected_by: str | None  # a member's name: "Connected by Mia"
    connected_at: datetime | None
    can_connect: bool  # live mode needs KROGER_REDIRECT_URI on the server
    demo: bool  # sample mode: a demo sign-in, and nothing reaches a real cart


class ConnectOut(BaseModel):
    authorize_url: str  # where the phone goes to sign in to Kroger
