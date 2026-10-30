#!/usr/bin/env python3
"""Prepare one task-owned feature branch from the latest remote development base."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shlex
import subprocess
import sys


class PreparationError(RuntimeError):
    """Report a safety condition that prevents automatic branch preparation."""


@dataclass(frozen=True)
class PreparationResult:
    """Describe the branch state produced by a successful preparation."""

    action: str
    branch: str
    base_ref: str
    head_before: str
    head_after: str
    remote_feature_sha: str | None
    push_mode: str
    push_expected_sha: str | None
    push_command: str
    adopt_command: str = "-"


@dataclass(frozen=True)
class RemoteFeature:
    """Describe the fetched remote feature branch relative to local HEAD."""

    sha: str | None
    adopt: bool


def git(
    repo: Path,
    *args: str,
    check: bool = True,
    capture_stderr: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run Git in one explicit working tree."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if capture_stderr else None,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise PreparationError(f"git {' '.join(args)} failed{suffix}")
    return result


def output(repo: Path, *args: str) -> str:
    """Return stripped stdout from a required Git command."""
    return git(repo, *args).stdout.strip()


def ref_exists(repo: Path, ref: str) -> bool:
    """Return whether an exact Git ref exists."""
    return git(repo, "show-ref", "--verify", "--quiet", ref, check=False).returncode == 0


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    """Return whether one revision is an ancestor of another."""
    return (
        git(
            repo,
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
            check=False,
        ).returncode
        == 0
    )


def current_branch(repo: Path) -> str | None:
    """Return the checked-out branch, or None for detached HEAD."""
    result = git(
        repo,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        check=False,
    )
    return result.stdout.strip() or None


def resolve_commit(repo: Path, revision: str) -> str:
    """Return the full commit SHA for a revision that must exist locally."""
    result = git(
        repo,
        "rev-parse",
        "--verify",
        "--quiet",
        f"{revision}^{{commit}}",
        check=False,
    )
    if result.returncode != 0:
        raise PreparationError(f"unknown commit: {revision}")
    return result.stdout.strip()


def patch_ids(repo: Path, base_ref: str, tip: str) -> list[str]:
    """Return sorted patch identities for the feature-local commits of one tip."""
    log = git(repo, "log", "-p", "--no-merges", "--no-color", f"{base_ref}..{tip}").stdout
    result = subprocess.run(
        ["git", "-C", str(repo), "patch-id", "--stable"],
        check=False,
        text=True,
        input=log,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise PreparationError(f"git patch-id failed: {result.stderr.strip()}")
    return sorted(line.split()[0] for line in result.stdout.splitlines() if line.strip())


def require_clean(repo: Path, *, ignore_submodules: bool = False) -> None:
    """Reject state that a rebase or branch switch could carry or overwrite."""
    arguments = ["status", "--porcelain", "--untracked-files=all"]
    if ignore_submodules:
        arguments.append("--ignore-submodules=all")
    changes = output(repo, *arguments)
    if changes:
        preview = ", ".join(line[3:] for line in changes.splitlines()[:5])
        raise PreparationError(
            "working tree is dirty; preserve the existing task and use a separate "
            f"worktree for new work (changed: {preview})"
        )


def require_no_git_operation(repo: Path) -> None:
    """Reject a checkout whose history operation requires deliberate recovery."""
    operation_paths = {
        "rebase": ("rebase-merge", "rebase-apply"),
        "merge": ("MERGE_HEAD",),
        "cherry-pick": ("CHERRY_PICK_HEAD",),
        "revert": ("REVERT_HEAD",),
        "bisect": ("BISECT_LOG",),
    }
    for operation, candidates in operation_paths.items():
        for candidate in candidates:
            raw_path = output(repo, "rev-parse", "--git-path", candidate)
            operation_path = Path(raw_path)
            if not operation_path.is_absolute():
                operation_path = repo / operation_path
            if operation_path.exists():
                raise PreparationError(
                    f"Git {operation} operation is already in progress; resolve or abort it first"
                )


def validate_branch_name(repo: Path, branch: str) -> None:
    """Reject protected or malformed feature branch names."""
    if git(repo, "check-ref-format", "--branch", branch, check=False).returncode != 0:
        raise PreparationError(f"invalid feature branch name: {branch}")


def fetch_remote(repo: Path, remote: str) -> None:
    """Refresh remote-tracking refs before making any freshness decision."""
    git(repo, "fetch", "--prune", remote)


def require_active_linear_history(repo: Path, base_ref: str) -> None:
    """Reject integrated branches and feature-local merge commits."""
    if is_ancestor(repo, "HEAD", base_ref):
        raise PreparationError(
            "feature branch is already integrated into the fetched base or has no "
            "task commit; create a new task branch instead of reusing it"
        )

    merges = output(repo, "rev-list", "--merges", f"{base_ref}..HEAD").splitlines()
    if merges:
        preview = ", ".join(commit[:12] for commit in merges[:3])
        raise PreparationError(
            "feature history contains a merge commit; preserve linear history by "
            f"recreating or deliberately rebasing the branch (commits: {preview})"
        )


def build_result(
    repo: Path,
    *,
    action: str,
    branch: str,
    base_ref: str,
    head_before: str,
    head_after: str,
    remote: str,
    remote_feature_sha: str | None,
) -> PreparationResult:
    """Attach the only safe push strategy for the observed remote revision."""
    branch_ref = f"refs/heads/{branch}"
    destination = f"HEAD:{branch_ref}"
    command = ["git", "-C", str(repo), "push"]
    adopt_command = "-"

    if action == "created":
        push_mode = "not-ready"
        push_expected_sha = None
        command = []
    elif action == "adopt-remote":
        push_mode = "adopt-remote"
        push_expected_sha = remote_feature_sha
        command = []
        adopt_command = shlex.join(
            ["git", "-C", str(repo), "reset", "--keep", str(remote_feature_sha)]
        )
    elif remote_feature_sha is None:
        push_mode = "create-only"
        push_expected_sha = None
        command.extend(
            [
                f"--force-with-lease={branch_ref}:",
                "--set-upstream",
                remote,
                destination,
            ]
        )
    elif remote_feature_sha == head_after:
        push_mode = "up-to-date"
        push_expected_sha = remote_feature_sha
        command = []
    elif is_ancestor(repo, remote_feature_sha, head_after):
        push_mode = "fast-forward"
        push_expected_sha = remote_feature_sha
        command.extend([remote, destination])
    else:
        push_mode = "force-with-lease"
        push_expected_sha = remote_feature_sha
        command.extend(
            [
                f"--force-with-lease={branch_ref}:{remote_feature_sha}",
                remote,
                destination,
            ]
        )

    return PreparationResult(
        action=action,
        branch=branch,
        base_ref=base_ref,
        head_before=head_before,
        head_after=head_after,
        remote_feature_sha=remote_feature_sha,
        push_mode=push_mode,
        push_expected_sha=push_expected_sha,
        push_command=shlex.join(command) if command else "-",
        adopt_command=adopt_command,
    )


def inspect_remote_feature(
    repo: Path,
    *,
    branch: str,
    base_name: str,
    remote: str,
    expect_remote_sha: str | None,
) -> RemoteFeature:
    """Classify the fetched remote feature branch before any local rewrite."""
    remote_feature_ref = f"refs/remotes/{remote}/{branch}"
    if not ref_exists(repo, remote_feature_ref):
        if expect_remote_sha is not None:
            raise PreparationError(
                f"expected {remote}/{branch} at {expect_remote_sha}, but the remote "
                "branch does not exist; stop for review"
            )
        return RemoteFeature(sha=None, adopt=False)

    remote_feature_sha = output(repo, "rev-parse", remote_feature_ref)
    if is_ancestor(repo, remote_feature_ref, base_name):
        raise PreparationError(
            f"{remote}/{branch} is already integrated into {base_name} "
            "or contains no task commit; create a new task branch"
        )

    if expect_remote_sha is not None:
        expected = resolve_commit(repo, expect_remote_sha)
        if expected != remote_feature_sha:
            raise PreparationError(
                f"{remote}/{branch} is at {remote_feature_sha}, not the expected "
                f"{expected}; the remote changed after the local rewrite, stop for review"
            )
        return RemoteFeature(sha=remote_feature_sha, adopt=False)

    if is_ancestor(repo, remote_feature_ref, "HEAD"):
        return RemoteFeature(sha=remote_feature_sha, adopt=False)

    # Equal patch sets mean neither side holds work the other lacks; only the
    # base differs, so the newer base decides which side is current.
    if patch_ids(repo, base_name, remote_feature_ref) == patch_ids(repo, base_name, "HEAD"):
        if is_ancestor(repo, base_name, remote_feature_ref) and not is_ancestor(
            repo, base_name, "HEAD"
        ):
            return RemoteFeature(sha=remote_feature_sha, adopt=True)
        raise PreparationError(
            f"{remote}/{branch} carries the same patches as local HEAD on a different "
            "base; if local HEAD is the intended rewrite (for example after an "
            f"interrupted push), rerun with --expect-remote-sha {remote_feature_sha}"
        )

    raise PreparationError(
        f"{remote}/{branch} contains commits absent from local HEAD; "
        "stop instead of overwriting another owner"
    )


def prepare(
    repo: Path,
    *,
    branch: str | None,
    remote: str = "origin",
    base: str = "dev",
    expect_remote_sha: str | None = None,
) -> PreparationResult:
    """Create or refresh one task-owned feature branch."""
    repo = repo.resolve()
    if output(repo, "rev-parse", "--is-inside-work-tree") != "true":
        raise PreparationError(f"not a Git working tree: {repo}")

    fetch_remote(repo, remote)
    base_ref = f"refs/remotes/{remote}/{base}"
    if not ref_exists(repo, base_ref):
        raise PreparationError(f"fetched base does not exist: {remote}/{base}")

    require_no_git_operation(repo)
    require_clean(repo)
    checked_out = current_branch(repo)
    protected = {base, "main"}
    base_name = f"{remote}/{base}"
    head_before = output(repo, "rev-parse", "HEAD")

    if checked_out is None or checked_out in protected:
        if not branch:
            location = "detached HEAD" if checked_out is None else checked_out
            raise PreparationError(
                f"{location} is not a feature branch; pass --branch for the new task"
            )
        if expect_remote_sha is not None:
            raise PreparationError(
                "--expect-remote-sha applies only to an existing task branch"
            )
        validate_branch_name(repo, branch)
        if branch in protected:
            raise PreparationError(f"protected branch cannot be a feature branch: {branch}")
        local_ref = f"refs/heads/{branch}"
        remote_ref = f"refs/remotes/{remote}/{branch}"
        if ref_exists(repo, local_ref) or ref_exists(repo, remote_ref):
            raise PreparationError(
                f"feature branch already exists locally or remotely: {branch}; "
                "do not reuse a branch without confirming task ownership"
            )
        git(repo, "switch", "--no-track", "-c", branch, base_name)
        head_after = output(repo, "rev-parse", "HEAD")
        return build_result(
            repo,
            action="created",
            branch=branch,
            base_ref=base_name,
            head_before=head_before,
            head_after=head_after,
            remote=remote,
            remote_feature_sha=None,
        )

    if branch and branch != checked_out:
        raise PreparationError(
            f"current branch is {checked_out}, not requested task branch {branch}"
        )

    remote_feature = inspect_remote_feature(
        repo,
        branch=checked_out,
        base_name=base_name,
        remote=remote,
        expect_remote_sha=expect_remote_sha,
    )
    remote_feature_sha = remote_feature.sha
    if remote_feature.adopt:
        return build_result(
            repo,
            action="adopt-remote",
            branch=checked_out,
            base_ref=base_name,
            head_before=head_before,
            head_after=head_before,
            remote=remote,
            remote_feature_sha=remote_feature_sha,
        )

    require_active_linear_history(repo, base_name)

    if is_ancestor(repo, base_name, "HEAD"):
        return build_result(
            repo,
            action="current",
            branch=checked_out,
            base_ref=base_name,
            head_before=head_before,
            head_after=head_before,
            remote=remote,
            remote_feature_sha=remote_feature_sha,
        )

    try:
        git(repo, "rebase", base_name)
    except PreparationError as error:
        raise PreparationError(
            f"rebase onto {base_name} did not complete; resolve or abort the rebase: {error}"
        ) from error

    head_after = output(repo, "rev-parse", "HEAD")
    require_active_linear_history(repo, base_name)
    return build_result(
        repo,
        action="rebased",
        branch=checked_out,
        base_ref=base_name,
        head_before=head_before,
        head_after=head_after,
        remote=remote,
        remote_feature_sha=remote_feature_sha,
    )


def format_result(result: PreparationResult, *, as_json: bool) -> str:
    """Render stable output for agents and shell integrations."""
    if as_json:
        return json.dumps(asdict(result), sort_keys=True)

    values = (
        ("branch", result.branch),
        ("base", result.base_ref),
        ("action", result.action),
        ("head_before", result.head_before),
        ("head_after", result.head_after),
        ("remote_feature_sha", result.remote_feature_sha or "-"),
        ("push_mode", result.push_mode),
        ("push_expected_sha", result.push_expected_sha or "-"),
        ("push_command", result.push_command),
        ("adopt_command", result.adopt_command),
    )
    return "\n".join(f"{key}={value}" for key, value in values)


def parse_args() -> argparse.Namespace:
    """Parse the feature preparation command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--branch")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--base", default="dev")
    parser.add_argument(
        "--expect-remote-sha",
        help="remote feature SHA that a deliberate local rewrite replaces",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Prepare the requested branch and report push-relevant state."""
    args = parse_args()
    try:
        result = prepare(
            args.repo,
            branch=args.branch,
            remote=args.remote,
            base=args.base,
            expect_remote_sha=args.expect_remote_sha,
        )
    except PreparationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(format_result(result, as_json=args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
