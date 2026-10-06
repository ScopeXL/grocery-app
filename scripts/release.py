#!/usr/bin/env python3
"""Release helpers used by the deploy skill (docs/PLAN.md §11.3, §11.10).

  release.py bump patch|minor|major   VERSION, CHANGELOG section + links, released.lock
  release.py tag [--trailer TEXT]     commit the release files, tag vX.Y.Z, push atomically

`tag` refuses unless the only changes since `just preflight` are the release files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO / "VERSION"
CHANGELOG = REPO / "CHANGELOG.md"
MIGRATIONS = REPO / "backend" / "src" / "dinnerbell" / "migrations"
LOCK = MIGRATIONS / "released.lock"
STAMP = REPO / ".git" / "dinnerbell-preflight"
RELEASE_FILES = {
    "VERSION",
    "CHANGELOG.md",
    "backend/src/dinnerbell/migrations/released.lock",
}
GITHUB = "https://github.com/ScopeXL/grocery-app"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


def fail(message: str) -> None:
    print(f"release: {message}", file=sys.stderr)
    raise SystemExit(1)


def current_version() -> str:
    version = VERSION_FILE.read_text().strip()
    if not SEMVER.match(version):
        fail(f"VERSION is not X.Y.Z: {version!r}")
    return version


def next_version(version: str, level: str) -> str:
    match = SEMVER.match(version)
    assert match
    major, minor, patch = (int(part) for part in match.groups())
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def unreleased_body(text: str) -> tuple[int, int, str]:
    start = text.index("## [Unreleased]")
    after = text.index("\n", start) + 1
    next_heading = text.find("\n## [", after)
    links = text.find("\n[Unreleased]:", after)
    ends = [pos for pos in (next_heading, links) if pos != -1]
    end = min(ends) if ends else len(text)
    return after, end, text[after:end]


def bump(level: str) -> None:
    old = current_version()
    new = next_version(old, level)
    text = CHANGELOG.read_text()
    after, end, body = unreleased_body(text)
    if not re.search(r"^- ", body, re.MULTILINE):
        fail("CHANGELOG [Unreleased] has no entries; write the release notes first.")
    today = dt.date.today().isoformat()
    text = text[:after] + f"\n## [{new}] - {today}\n" + body.rstrip("\n") + "\n" + text[end:]
    text = re.sub(r"^\[Unreleased\]: .*\n?", "", text, flags=re.MULTILINE).rstrip("\n") + "\n"
    first_release = old == "0.0.0"
    compare = f"{GITHUB}/releases/tag/v{new}" if first_release else f"{GITHUB}/compare/v{old}...v{new}"
    text += f"\n[Unreleased]: {GITHUB}/compare/v{new}...HEAD\n[{new}]: {compare}\n"
    text = re.sub(r"\n{3,}", "\n\n", text)
    CHANGELOG.write_text(text)
    VERSION_FILE.write_text(new + "\n")
    locked = {
        line.split()[0]
        for line in LOCK.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    added = []
    for path in sorted((MIGRATIONS / "versions").glob("*.py")):
        revision = path.name.split("_", 1)[0]
        if revision not in locked:
            digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            added.append(f"{revision} {digest}")
    if added:
        with LOCK.open("a") as handle:
            handle.write("\n".join(added) + "\n")
    print(f"Bumped {old} -> {new}. Locked {len(added)} migration(s). Review CHANGELOG.md.")


def release_notes(version: str) -> str:
    text = CHANGELOG.read_text()
    start = text.index(f"## [{version}]")
    after = text.index("\n", start) + 1
    end = text.find("\n## [", after)
    links = text.find("\n[Unreleased]:", after)
    ends = [pos for pos in (end, links) if pos != -1]
    return text[after : min(ends) if ends else len(text)].strip()


def tag(trailer: str | None) -> None:
    if not STAMP.is_file():
        fail("run `just preflight` first")
    stamped_tree = STAMP.read_text().strip()
    changed = set(git("diff", "--name-only", stamped_tree).splitlines())
    untracked = set(git("ls-files", "--others", "--exclude-standard").splitlines())
    unexpected = (changed | untracked) - RELEASE_FILES
    if unexpected:
        fail("files changed since preflight: " + ", ".join(sorted(unexpected)))
    version = current_version()
    name = f"v{version}"
    if git("tag", "--list", name):
        fail(f"tag {name} already exists")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        fail("releases are tagged on main")
    git("add", *sorted(p for p in RELEASE_FILES if (REPO / p).exists()))
    message = f"Release {name}"
    if trailer:
        message += f"\n\n{trailer}"
    git("commit", "-m", message)
    git("tag", "-a", name, "-m", f"Dinner Bell {name}\n\n{release_notes(version)}")
    subprocess.run(["git", "push", "--atomic", "origin", "main", name], cwd=REPO, check=True)
    STAMP.unlink()
    print(f"Tagged and pushed {name}.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="release.py")
    sub = parser.add_subparsers(dest="command", required=True)
    bump_parser = sub.add_parser("bump")
    bump_parser.add_argument("level", choices=["patch", "minor", "major"])
    tag_parser = sub.add_parser("tag")
    tag_parser.add_argument("--trailer")
    args = parser.parse_args()
    if args.command == "bump":
        bump(args.level)
    else:
        tag(args.trailer)


if __name__ == "__main__":
    main()
