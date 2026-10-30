#!/usr/bin/env python3
"""Point this checkout and its initialized submodules at the repository-owned Git hooks.

This script is synchronized into standalone subproject clones and must depend
only on the standard library.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


HOOKS_PATH = "skills/guard-git-operations/hooks"
REQUIRED_HOOKS = ("pre-push",)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def repositories(root: Path) -> list[Path]:
    """Return this checkout followed by every initialized submodule checkout."""
    found = [root]
    listing = git(root, "config", "--file", ".gitmodules", "--get-regexp", r"\.path$")
    for line in listing.stdout.splitlines():
        path = root / line.split(maxsplit=1)[1]
        if git(path, "rev-parse", "--show-toplevel").stdout.strip() == str(path.resolve()):
            found.append(path)
    return found


def custom_hooks(repo: Path) -> list[str]:
    """Return active hooks in the default hooks directory that hooksPath would hide."""
    raw = git(repo, "rev-parse", "--git-path", "hooks").stdout.strip()
    directory = Path(raw) if Path(raw).is_absolute() else repo / raw
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if p.is_file() and not p.name.endswith(".sample"))


def inspect(repo: Path) -> list[str]:
    """Return the reasons this repository's guard is not active."""
    problems: list[str] = []
    configured = git(repo, "config", "--get", "core.hooksPath").stdout.strip()
    if configured != HOOKS_PATH:
        problems.append(f"core.hooksPath is {configured or 'unset'}, expected {HOOKS_PATH}")
    for hook in REQUIRED_HOOKS:
        path = repo / HOOKS_PATH / hook
        if not path.is_file():
            problems.append(f"{path} is missing in this checkout")
        elif not os.access(path, os.X_OK):
            problems.append(f"{path} is not executable")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--check", action="store_true", help="report without changing Git config")
    parser.add_argument("--force", action="store_true", help="replace a different hooksPath or hide custom hooks")
    args = parser.parse_args()

    failed = False
    for repo in repositories(args.root.resolve()):
        if args.check:
            problems = inspect(repo)
            for problem in problems:
                print(f"{repo}: {problem}", file=sys.stderr)
            failed = failed or bool(problems)
            continue
        configured = git(repo, "config", "--get", "core.hooksPath").stdout.strip()
        hidden = custom_hooks(repo)
        if not args.force and ((configured and configured != HOOKS_PATH) or hidden):
            reason = f"core.hooksPath={configured}" if configured else f"custom hooks {hidden}"
            print(f"{repo}: refusing to override {reason}; rerun with --force", file=sys.stderr)
            failed = True
            continue
        git(repo, "config", "core.hooksPath", HOOKS_PATH)
        missing = inspect(repo)
        status = "installed" if not missing else "configured; " + "; ".join(missing)
        print(f"{repo}: {status}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
