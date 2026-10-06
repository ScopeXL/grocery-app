"""The running version (docs/adr/0019-versioning.md).

In the image, /app/build-info.json is written at build time. In development, the version is
read from the repo's VERSION file and the revision is "dev".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

BUILD_INFO_PATH = Path(os.environ.get("DINNERBELL_BUILD_INFO", "/app/build-info.json"))


@dataclass(frozen=True, slots=True)
class BuildInfo:
    version: str
    revision: str
    created: str | None


@cache
def build_info() -> BuildInfo:
    if BUILD_INFO_PATH.is_file():
        data = json.loads(BUILD_INFO_PATH.read_text())
        return BuildInfo(
            version=str(data["version"]),
            revision=str(data.get("revision", "unknown")),
            created=data.get("created"),
        )
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "VERSION"
        if candidate.is_file():
            return BuildInfo(version=candidate.read_text().strip(), revision="dev", created=None)
    return BuildInfo(version="0.0.0", revision="dev", created=None)
