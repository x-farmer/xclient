---
name: prepare-feature-branch
description: Start or resume x-farmer feature work from the latest origin/dev while enforcing clean-tree, task-lifecycle, linear-history, and safe-push rules.
---

# Prepare Feature Branch

## When to Use This Skill

Use this skill before editing for a new implementation task, before resuming an
existing feature task, and before pushing a feature branch. Read and follow
`docs/standards/git-workflow.md` first.

This is a freshness, lifecycle, linear-history, and isolation gate. It does not
commit, push, stash, discard changes, resolve conflicts, or decide that an old
branch belongs to a new task.

## New Task

Confirm that the current branch is `dev`, `main`, or detached and that the
working tree contains no changes owned by another task. Choose a unique branch
name for the task that follows the Branch Naming section of
`docs/standards/git-workflow.md`, then run from the applicable Git working
tree:

```bash
python3 skills/prepare-feature-branch/scripts/prepare-feature-branch.py \
  --branch <type>/<task-name>
```

The script fetches first, rejects dirty state or branch-name collisions, and
creates the feature branch from the fetched `origin/dev` without making
`origin/dev` its upstream.

The empty branch is returned as `push_mode=not-ready` with no push command.
After the first task commit is validated, rerun the gate and use its authorized
`create-only` push command. The empty expected lease rejects a branch claimed
by another machine after the fetch.

If the current feature branch belongs to a completed or different task, do not
reuse it. Return to a clean base checkout or create a separate worktree from
`origin/dev`, then run the new-task flow there.

## Resume Current Task

While already on the feature branch owned by the current task, run:

```bash
python3 skills/prepare-feature-branch/scripts/prepare-feature-branch.py
```

The script always fetches before evaluating freshness. It stops on a dirty
tree, a remote-only feature commit, a local or remote feature tip already
integrated into `origin/dev`, or any merge commit in feature-local history. If
`origin/dev` is not already an ancestor of `HEAD`, it rebases the branch onto
that fetched base.

If rebase reports conflicts, preserve the conflict state, explain the affected
paths, and resolve them only within the current task's scope. Rerun the relevant
validation after the rebase completes.

## Other Working Trees

The default repository is the current checkout. When this repository is the
x-farmer-dev root, pass an affected submodule path explicitly:

```bash
python3 skills/prepare-feature-branch/scripts/prepare-feature-branch.py \
  --repo src/<project> --branch <type>/<task-name>
```

Run the gate independently for every affected Git working tree. Prepare the
root branch before moving subproject branches so submodule state does not make
the root appear dirty during its initial gate.

## Deliberate Rewrites And Remote Rebases

The gate refuses to overwrite a remote feature branch that is not an ancestor
of local HEAD. Two legitimate situations need an explicit path:

- A deliberate local rewrite of published history, such as collapsing the root
  branch into one integration commit or resuming after a rebase whose push was
  interrupted. Record the remote feature SHA observed before the rewrite and
  rerun with `--expect-remote-sha <sha>`. The gate proceeds only when the fetched
  remote branch still equals that SHA and emits a force-with-lease bound to it.
  Never pass a SHA you did not observe before your own rewrite.
- A rebase performed on the server, such as GitHub's "Update branch" with
  rebase. When the remote branch carries exactly the same patches as local HEAD
  on the newer `origin/dev`, the gate reports `action=adopt-remote` and an
  `adopt_command` that moves local HEAD to the remote SHA. Run that command, then
  rerun the gate.

Remote commits whose content is absent locally always stop the gate.

## Before Push

After committing and before every push, rerun the resume command in the working
tree being pushed. If it rebases any commit, rerun the validation appropriate
to that project before pushing.

The gate prints `push_mode`, `push_expected_sha`, and the exact `push_command`
permitted by the fetched state. Use `--json` for machine-readable output. After
explicit push authorization, execute only the emitted command:

- `create-only`: first publication with an empty expected lease;
- `fast-forward`: normal push with an explicit destination ref;
- `force-with-lease`: a rebase rewrote published history, using the exact
  fetched feature SHA; or
- `up-to-date`: no push is needed and `push_command=-`.

A newly created branch with no task commit reports `not-ready` and also has no
push command. `adopt-remote` has no push command; run its `adopt_command`
instead.

If the remote feature branch has changed since the fetch, the lease fails. Stop
and review; never fall back to `--force`.

## Safety Stops

Stop without changing local history when:

- the fetch fails or `origin/dev` is unavailable;
- the working tree is dirty;
- the requested branch already exists locally or remotely;
- the current branch is not owned by the current task;
- the local or remote feature tip is already integrated into `origin/dev`;
- feature-local history contains a merge commit;
- the remote feature branch contains content absent locally;
- `--expect-remote-sha` does not match the fetched remote feature SHA; or
- a rebase would affect work outside the task's scope.

Git cannot identify squash- or rebase-merged pull requests from ancestry alone.
If the associated pull request is merged or closed, treat the branch as
completed and start a new task branch even when this local gate cannot infer it.
