#!/usr/bin/env python3
"""VERSION is the only version (docs/adr/0019-versioning.md); everything else stays 0.0.0."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
problems: list[str] = []

version = (REPO / "VERSION").read_text().strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    problems.append(f"VERSION must be X.Y.Z (found {version!r})")

pyproject = tomllib.loads((REPO / "backend" / "pyproject.toml").read_text())
if pyproject["project"]["version"] != "0.0.0":
    problems.append("backend/pyproject.toml version must stay 0.0.0 (VERSION is the source)")

package = json.loads((REPO / "frontend" / "package.json").read_text())
if package.get("version") != "0.0.0":
    problems.append("frontend/package.json version must stay 0.0.0 (VERSION is the source)")

if "## [Unreleased]" not in (REPO / "CHANGELOG.md").read_text():
    problems.append("CHANGELOG.md needs an ## [Unreleased] section")

if problems:
    print("\n".join(problems), file=sys.stderr)
    sys.exit(1)
print(f"Release metadata OK (VERSION {version}).")
