#!/usr/bin/env python3
"""Decide whether an agent shell command complies with the x-farmer Git delivery policy.

This script is synchronized into standalone subproject clones, so it must not
import anything outside the Python standard library or its own directory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


ROOT_REPOSITORY = "x-farmer/x-farmer-dev"
PROTECTED_BRANCHES = {"dev", "main"}
REQUIRED_BASE = "dev"
SEPARATORS = {";", "&", "&&", "|", "||", "(", ")", "\n"}
WRAPPERS = {"env", "sudo", "command", "time", "nohup", "exec"}
SHELLS = {"bash", "sh", "zsh", "dash"}
GITHUB_URL = re.compile(r"github\.com[:/](?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?/?$")
SEVERITY = {"allow": 0, "ask": 1, "deny": 2}
GH_REPO_FLAGS = {"-R", "--repo"}


@dataclass(frozen=True)
class Decision:
    """The hook verdict for one command and the reason shown to the agent."""

    permission: str
    reason: str = ""


ALLOW = Decision("allow")


def deny(reason: str) -> Decision:
    return Decision("deny", reason)


def ask(reason: str) -> Decision:
    return Decision("ask", reason)


def strictest(decisions: list[Decision]) -> Decision:
    """Return the most restrictive decision; deny outranks ask outranks allow."""
    return max(decisions, key=lambda decision: SEVERITY[decision.permission], default=ALLOW)


def split_segments(command: str) -> list[list[str]]:
    """Split a shell command line into simple commands; redirections are dropped."""
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    segments: list[list[str]] = [[]]
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in SEPARATORS:
            segments.append([])
        elif token and set(token) <= set("<>&"):
            skip_next = True
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def git_output(repo: Path, *args: str) -> str | None:
    """Return Git stdout for read-only repository inspection, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def current_branch(repo: Path) -> str | None:
    return git_output(repo, "symbolic-ref", "--quiet", "--short", "HEAD") or None


def is_repository(repo: Path) -> bool:
    return git_output(repo, "rev-parse", "--is-inside-work-tree") == "true"


def operation_in_progress(repo: Path) -> bool:
    for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        raw = git_output(repo, "rev-parse", "--git-path", name)
        if raw and (Path(raw) if Path(raw).is_absolute() else repo / raw).exists():
            return True
    return False


def github_slug(value: str) -> str | None:
    """Return owner/name from a GitHub URL, a HOST/owner/name, or an owner/name value."""
    value = value.strip()
    match = GITHUB_URL.search(value)
    if match:
        return match.group("slug")
    parts = [part for part in value.split("/") if part]
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


def repository_slug(repo: Path) -> str | None:
    url = git_output(repo, "config", "--get", "remote.origin.url")
    return github_slug(url) if url else None


def option_value(args: list[str], names: set[str]) -> str | None:
    """Return the value of the last occurrence of a long or short option."""
    found = None
    for index, arg in enumerate(args):
        for name in names:
            if arg == name and index + 1 < len(args):
                found = args[index + 1]
            elif arg.startswith(f"{name}=") and name.startswith("--"):
                found = arg.split("=", 1)[1]
    return found


def has_flag(args: list[str], long: set[str], short: str = "") -> bool:
    """Return whether a long flag or a short letter inside a flag cluster is present."""
    for arg in args:
        if arg in long or any(arg.startswith(f"{name}=") for name in long):
            return True
        if short and arg.startswith("-") and not arg.startswith("--") and short in arg[1:]:
            return True
    return False


def evaluate_git(args: list[str], cwd: Path) -> Decision:
    """Apply the Git policy to one git invocation."""
    repo = cwd
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option == "-C" and index + 1 < len(args):
            repo = (repo / args[index + 1]).resolve()
            index += 2
            continue
        if option == "-c" and index + 1 < len(args):
            if args[index + 1].lower().startswith("core.hookspath"):
                return deny("overriding core.hooksPath disables the pre-push guard")
            index += 2
            continue
        index += 1
    if index >= len(args):
        return ALLOW
    subcommand, rest = args[index], args[index + 1 :]

    if subcommand == "push":
        return evaluate_push(rest, repo)
    if subcommand == "merge":
        if has_flag(rest, {"--ff-only", "--abort", "--continue", "--quit"}):
            return ALLOW
        return deny("merge only with --ff-only; feature history must stay linear (rebase instead)")
    if subcommand == "pull":
        disabled = any(arg in {"--no-rebase", "--rebase=false", "--no-ff", "--ff"} for arg in rest)
        if not disabled and has_flag(rest, {"--ff-only", "--rebase"}, "r"):
            return ALLOW
        return deny("pull only with --ff-only or --rebase; never create merge commits")
    if subcommand == "stash":
        if rest and rest[0] in {"list", "show"}:
            return ALLOW
        return deny("do not stash; use a separate worktree instead of moving another task's changes")
    if subcommand in {"commit", "rebase"}:
        if subcommand == "rebase" and has_flag(
            rest, {"--continue", "--abort", "--skip", "--quit", "--edit-todo", "--show-current-patch"}
        ):
            return ALLOW
        if not is_repository(repo) or operation_in_progress(repo):
            return ALLOW
        branch = current_branch(repo)
        if branch is None or branch in PROTECTED_BRANCHES:
            location = "detached HEAD" if branch is None else branch
            return deny(f"{subcommand} on {location} is not allowed; work on a task feature branch")
        return ALLOW
    if subcommand == "reset" and "--hard" in rest:
        return ask("git reset --hard discards local work")
    if subcommand == "clean" and has_flag(rest, {"--force"}, "f"):
        return ask("git clean -f deletes untracked files")
    if subcommand == "branch" and has_flag(rest, {"--delete"}, "D"):
        return ask("deleting a branch can lose unpushed work")
    if subcommand in {"checkout", "restore"} and ("." in rest or "--" in rest) and "--staged" not in rest:
        return ask(f"git {subcommand} on paths discards local changes")
    return ALLOW


def evaluate_push(args: list[str], repo: Path) -> Decision:
    """Allow only the explicit, lease-bound pushes the preparation gate emits."""
    if has_flag(args, {"--no-verify"}):
        return deny("--no-verify skips the pre-push guard")
    if has_flag(args, {"--force"}, "f"):
        return deny("never force-push; use the force-with-lease command emitted by the gate")
    if has_flag(args, {"--mirror", "--all", "--prune"}):
        return deny("push only the task branch with the gate's explicit refspec")
    for arg in args:
        if arg == "--force-with-lease" or (
            arg.startswith("--force-with-lease=") and ":" not in arg.split("=", 1)[1]
        ):
            return deny("a lease must name the ref and expected SHA; use the gate's push_command")
    if has_flag(args, {"--delete"}, "d"):
        return ask("deleting a remote branch")

    positional: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg in {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}:
            skip = True
            continue
        if not arg.startswith("-"):
            positional.append(arg)
    refspecs = positional[1:]
    if not refspecs:
        return deny("push only with the explicit push_command emitted by prepare-feature-branch")

    branch = current_branch(repo) if is_repository(repo) else None
    for refspec in refspecs:
        if refspec.startswith("+"):
            return deny("a + refspec force-pushes; use the gate's lease-bound command")
        if refspec.startswith(":"):
            return ask("deleting a remote branch")
        source, _, destination = refspec.partition(":")
        destination = destination or source
        if destination in {"HEAD", "@"}:
            destination = branch or destination
        name = destination.removeprefix("refs/heads/")
        if name in PROTECTED_BRANCHES:
            return deny(f"direct push to {name} is not allowed; merge through a pull request")
    return ALLOW


def evaluate_gh(args: list[str], cwd: Path) -> Decision:
    """Apply the pull request policy to one gh invocation."""
    words = [arg for arg in args if not arg.startswith("-")]
    if words[:1] == ["api"]:
        joined = " ".join(args)
        if re.search(r"pulls/\d+/merge\b", joined) or "mergePullRequest" in joined:
            return deny("merge pull requests only with gh pr merge under the delivery policy")
        return ALLOW
    if words[:1] != ["pr"] or len(words) < 2:
        return ALLOW
    action = words[1]
    explicit = option_value(args, GH_REPO_FLAGS)
    slug = github_slug(explicit) if explicit else repository_slug(cwd)

    if action == "merge":
        if slug is None:
            return ask("cannot determine which repository this gh pr merge targets")
        if slug.lower() == ROOT_REPOSITORY:
            return deny("only the platform owner merges root pull requests")
        if has_flag(args, {"--squash", "--merge", "--admin"}, "") or any(
            arg in {"-s", "-m"} for arg in args
        ):
            return deny("component pull requests merge only with --rebase")
        if not has_flag(args, {"--rebase"}) and "-r" not in args:
            return deny("component pull requests merge only with --rebase")
        if not has_flag(args, {"--match-head-commit"}):
            return deny("bind the merge to the tested head with --match-head-commit <sha>")
        return ALLOW
    if action in {"create", "edit"}:
        base = option_value(args, {"--base", "-B"})
        if action == "create" and base != REQUIRED_BASE:
            return deny(f"pull requests target {REQUIRED_BASE}; pass --base {REQUIRED_BASE}")
        if action == "edit" and base is not None and base != REQUIRED_BASE:
            return deny(f"pull requests target {REQUIRED_BASE}")
    return ALLOW


def evaluate(command: str, cwd: Path, depth: int = 0) -> Decision:
    """Return the strictest decision across every simple command in a command line."""
    decisions: list[Decision] = []
    for segment in split_segments(command):
        while segment and ("=" in segment[0] and not segment[0].startswith("-") or segment[0] in WRAPPERS):
            segment = segment[1:]
        if not segment:
            continue
        program = os.path.basename(segment[0])
        if program == "cd" and len(segment) > 1:
            cwd = (cwd / os.path.expanduser(segment[1])).resolve()
        elif program in SHELLS and "-c" in segment and depth < 3:
            position = segment.index("-c")
            if position + 1 < len(segment):
                decisions.append(evaluate(segment[position + 1], cwd, depth + 1))
        elif program == "git":
            decisions.append(evaluate_git(segment[1:], cwd))
        elif program == "gh":
            decisions.append(evaluate_gh(segment[1:], cwd))
    return strictest(decisions)


def read_request(raw: str) -> tuple[str | None, Path]:
    """Extract the shell command and working directory from a Cursor or Claude hook payload."""
    payload = json.loads(raw or "{}")
    tool = payload.get("tool_name")
    if tool is not None and tool != "Bash":
        return None, Path.cwd()
    command = payload.get("command") or (payload.get("tool_input") or {}).get("command")
    cwd = Path(payload.get("cwd") or os.getcwd())
    return command, cwd


def render(decision: Decision, output_format: str) -> str:
    """Encode a decision in the hook protocol of the calling tool."""
    message = f"x-farmer Git policy: {decision.reason}" if decision.reason else ""
    if output_format == "claude":
        if decision.permission == "allow":
            return ""
        return json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision.permission,
                    "permissionDecisionReason": message,
                }
            }
        )
    if decision.permission == "allow":
        return json.dumps({"permission": "allow"})
    return json.dumps(
        {"permission": decision.permission, "user_message": message, "agent_message": message}
    )


def main() -> int:
    """Read one hook payload from stdin and print the tool-specific verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["cursor", "claude"], required=True)
    args = parser.parse_args()
    try:
        command, cwd = read_request(sys.stdin.read())
        decision = evaluate(command, cwd) if command else ALLOW
    except Exception as error:  # noqa: BLE001 - a guard bug must not block unrelated commands
        print(f"guard-command: internal error, allowing: {error}", file=sys.stderr)
        decision = ALLOW
    rendered = render(decision, args.format)
    if rendered:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
