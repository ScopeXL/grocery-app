#!/usr/bin/env python3
"""Private-terms scan (docs/adr/0017-privacy-guardrails.md).

Looks for household-specific values (ZIP, store ID, names, street, domain, hosts, IPs, emails,
local paths) listed in a private file that never enters the repo or the image. It reports
`where: private term #n` and NEVER prints a term.

  private_scan.py setup          create the list, one category at a time
  private_scan.py staged         staged files (pre-commit hook)
  private_scan.py msg FILE       a commit message (commit-msg hook)
  private_scan.py range SPEC     commits about to be pushed (pre-push hook), e.g. A..B
  private_scan.py tree           the working tree (tracked + untracked, not ignored)
  private_scan.py history        every commit, message and tag in the repository
  private_scan.py context REF    the files `git archive REF` sends to docker build
  private_scan.py image IMAGE    a built image's labels, environment and layer history

Exit codes: 0 clean, 1 matches found, 2 no list (hook modes only warn).
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIST_PATHS = [
    Path.home() / ".config" / "dinner-bell" / "private-terms.txt",
    REPO / ".private" / "private-terms.txt",
]
HOOK_MODES = {"staged", "msg", "range"}
MAX_BYTES = 2_000_000
CATEGORIES = [
    "ZIP code(s) of your store and home",
    "Kroger store location ID(s)",
    "household member first names, and your surname",
    "street address(es)",
    "your domain and the app's subdomain",
    "Portainer host name(s) and IP address(es)",
    "home network ranges (e.g. 192.168.1.)",
    "this Mac's username and home folder path",
    "personal email addresses",
]


def git(*args: str, text: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=text, check=True
    )
    return result.stdout


def git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=True).stdout


def load_terms() -> list[str] | None:
    for path in LIST_PATHS:
        if path.is_file():
            terms = [
                line.strip()
                for line in path.read_text().splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            return terms or None
    return None


def compile_terms(terms: list[str]) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for term in terms:
        pattern = re.escape(term)
        if term[:1].isalnum():
            pattern = r"(?<![A-Za-z0-9])" + pattern
        if term[-1:].isalnum():
            pattern += r"(?![A-Za-z0-9])"
        patterns.append(re.compile(pattern, re.IGNORECASE))
    return patterns


def public_identity() -> set[str]:
    """The owner's intentionally public git identity (also the LICENSE copyright holder)."""
    names: set[str] = set()
    for key in ("user.name", "user.email"):
        try:
            value = git("config", key).strip()
        except subprocess.CalledProcessError:
            continue
        if value:
            names.add(value)
    return names


class Scanner:
    def __init__(self, patterns: list[re.Pattern[str]]) -> None:
        self.patterns = patterns
        self.hits: list[str] = []
        self.identity = public_identity()

    def text(self, where: str, content: str, *, path: str | None = None) -> None:
        for number, line in enumerate(content.splitlines(), 1):
            if path == "LICENSE" and line.startswith("Copyright"):
                continue  # the MIT copyright line is an intended public identity
            for index, pattern in enumerate(self.patterns, 1):
                if pattern.search(line):
                    self.hits.append(f"{where}:{number}: private term #{index}")

    def blob(self, where: str, data: bytes, *, path: str) -> None:
        if len(data) > MAX_BYTES or b"\0" in data[:8192]:
            return  # binary or huge: not text we can scan
        self.text(where, data.decode("utf-8", errors="replace"), path=path)

    def identity_field(self, where: str, value: str) -> None:
        if value in self.identity:
            return
        self.text(where, value)

    def commit(self, sha: str) -> None:
        short = sha[:10]
        fields = git("log", "-1", "--format=%an%x00%ae%x00%cn%x00%ce", sha).strip().split("\0")
        for label, value in zip(("author", "author email", "committer", "committer email"), fields):
            self.identity_field(f"commit {short} {label}", value)
        self.text(f"commit {short} message", git("log", "-1", "--format=%B", sha))
        diff = git("show", "--format=", "--unified=0", "--no-color", "--no-ext-diff", sha)
        current = "?"
        for line in diff.splitlines():
            if line.startswith("+++ "):
                current = line[6:] if line.startswith("+++ b/") else line[4:]
                self.text(f"commit {short} path", current)
            elif line.startswith("+") and not line.startswith("+++"):
                self.text(f"commit {short} {current}", line[1:], path=current)


def scan(mode: str, args: list[str], scanner: Scanner) -> None:
    if mode == "staged":
        for path in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0"):
            if path:
                scanner.text("staged path", path)
                scanner.blob(f"staged {path}", git_bytes("show", f":{path}"), path=path)
    elif mode == "msg":
        message = Path(args[0]).read_text()
        body = "\n".join(line for line in message.splitlines() if not line.startswith("#"))
        scanner.text("commit message", body)
    elif mode == "range":
        for sha in git("rev-list", *args).split():
            scanner.commit(sha)
    elif mode == "tree":
        for path in git("ls-files", "-co", "--exclude-standard", "-z").split("\0"):
            full = REPO / path
            if path and full.is_file():
                scanner.text("path", path)
                scanner.blob(path, full.read_bytes(), path=path)
    elif mode == "history":
        for sha in git("rev-list", "--all").split():
            scanner.commit(sha)
        for tag in git("for-each-ref", "refs/tags", "--format=%(refname:short)").split():
            scanner.text(f"tag {tag}", git("for-each-ref", f"refs/tags/{tag}", "--format=%(contents)"))
    elif mode == "context":
        archive = git_bytes("archive", "--format=tar", args[0])
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar.getmembers():
                if member.isfile():
                    handle = tar.extractfile(member)
                    if handle is not None:
                        scanner.text("context path", member.name)
                        scanner.blob(f"context {member.name}", handle.read(), path=member.name)
    elif mode == "image":
        docker = os.environ.get("DOCKER", "docker")
        info = json.loads(
            subprocess.run([docker, "image", "inspect", args[0]], capture_output=True, text=True, check=True).stdout
        )[0]
        config = info.get("Config") or {}
        scanner.text("image labels", json.dumps(config.get("Labels") or {}, indent=1))
        scanner.text("image env", "\n".join(config.get("Env") or []))
        history = subprocess.run(
            [docker, "history", "--no-trunc", "--format", "{{.CreatedBy}}", args[0]],
            capture_output=True, text=True, check=True,
        ).stdout
        scanner.text("image history", history)
    else:
        raise SystemExit(f"unknown mode: {mode}")


def setup() -> int:
    existing = next((p for p in LIST_PATHS if p.is_file()), None)
    if existing:
        print(f"Private-terms list found ({existing}). Edit it directly to add terms.")
        return 0
    target = LIST_PATHS[0]
    if not sys.stdin.isatty():
        print(f"No private-terms list yet. Create {target} with one term per line;")
        print("categories: " + "; ".join(CATEGORIES) + ".")
        return 0
    print("Dinner Bell keeps household details out of the public repo by scanning for them.")
    print(f"Enter terms for each category (comma-separated, Enter to skip). Saved to {target}.")
    lines = ["# Dinner Bell private terms: one per line. Never commit this file."]
    for category in CATEGORIES:
        answer = input(f"  {category}: ").strip()
        lines.extend(term.strip() for term in answer.split(",") if term.strip())
    if len(lines) == 1:
        print("No terms entered; nothing saved.")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n")
    target.chmod(0o600)
    print(f"Saved {len(lines) - 1} terms.")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    mode, args = argv[0], argv[1:]
    if mode == "setup":
        return setup()
    terms = load_terms()
    if terms is None:
        message = (
            "No private-terms list found (~/.config/dinner-bell/private-terms.txt). "
            "Run `just setup` to create one."
        )
        if mode in HOOK_MODES:
            print(f"warning: {message}", file=sys.stderr)
            return 0
        print(f"error: {message}", file=sys.stderr)
        return 2
    scanner = Scanner(compile_terms(terms))
    scan(mode, args, scanner)
    if scanner.hits:
        for hit in sorted(set(scanner.hits)):
            print(hit)
        print(
            f"{len(set(scanner.hits))} private-term match(es). Remove them; never allowlist them.",
            file=sys.stderr,
        )
        return 1
    print(f"Private-terms scan clean ({mode}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
