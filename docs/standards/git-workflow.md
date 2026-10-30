# Git Collaboration Workflow

This standard defines the Git isolation and freshness rules for developers and
AI agents working on xFarm. Its purpose is to prevent concurrent tasks from
silently sharing state and to ensure that integration decisions use the latest
known `dev` revision.

## Invariants

- `origin/dev`, after a successful fetch, is the authoritative development
  base. A local `dev` branch is not evidence that the remote base is current.
- One task has one feature branch and one owner at a time. Separate concurrent
  tasks use separate worktrees.
- A feature branch belongs to one task only. A completed, merged, closed, or
  otherwise unrelated feature branch must not be reused for a new task.
- Feature-local history is linear. Do not merge `dev` or another feature branch
  into a task branch; refresh it with the preparation gate's rebase path.
- Development changes are not made directly on `dev` or `main`.
- A rebase is allowed only with a clean working tree and after remote refs have
  been refreshed. Agents must not automatically stash another task's work.
- The root repository and every affected subproject are separate Git working
  trees. Freshness must be established independently in each one.

These invariants reduce accidental overlap; they do not make a branch
permanently current. Another pull request can update `dev` immediately after a
fetch, so the merge-time gate described in [GitHub Merge Gate](#github-merge-gate)
remains the final integration decision.

## Branch Naming

Feature branches use `<type>/<task-name>` or `<type>/<developer>/<task-name>`:

- `<type>` is the Conventional Commits type of the task's primary change, such
  as `feat`, `fix`, `docs`, `ci`, `refactor`, `test`, or `chore`; see
  [`conventional-commits.md`](conventional-commits.md).
- `<task-name>` is a short kebab-case summary of the task, for example
  `desktop-ux-polish`.
- `<developer>` is optional and names the human owner. AI agents omit it by
  default and never use a tool-specific prefix such as `codex/` or `cursor/`.

## Required Checkpoints

### Starting a new task

Before editing code, configuration, scripts, tests, or documentation:

1. Fetch and prune the remote refs.
2. Verify that the working tree is clean. A dirty tree must be resolved by its
   owner or left untouched while the new task starts in a separate worktree.
3. Create a new feature branch directly from the fetched `origin/dev`, named
   as described in [Branch Naming](#branch-naming).
4. Do not configure the new branch to track `origin/dev`; its upstream is set
   to its same-named remote branch on first push.

The canonical root workflow is:

```bash
python3 skills/prepare-feature-branch/scripts/prepare-feature-branch.py \
  --branch <type>/<task-name>
```

The creation result is `push_mode=not-ready` with no push command because an
empty task branch must not be published. Make and validate the task commit,
rerun the gate, and use the newly emitted `create-only` command only after push
is authorized. Its empty expected lease makes the first push fail if another
machine created the branch after the fetch.

When the existing worktree is dirty or another task needs to run concurrently,
create a separate worktree from `origin/dev` instead of moving or stashing the
existing changes.

### Resuming the same task

Before editing an existing task-owned feature branch:

1. Fetch and prune the remote refs.
2. Stop if the working tree is dirty.
3. Stop if the remote feature branch contains a commit absent from the local
   branch; this indicates another owner or an unincorporated remote update.
4. Stop if the local or remote feature tip is already integrated into the
   fetched `origin/dev`; the task branch is complete and must not be reused.
5. Stop if feature-local history contains a merge commit.
6. If the fetched `origin/dev` is not an ancestor of the feature branch, rebase
   the feature branch onto `origin/dev`.
7. Resolve any rebase conflict deliberately and rerun affected validation.

Run the same preparation command without `--branch` while already on the
task-owned feature branch:

```bash
python3 skills/prepare-feature-branch/scripts/prepare-feature-branch.py
```

Branch naming alone does not establish task ownership. If the current feature
branch belongs to an earlier task, start a fresh branch or worktree instead.

### Before every push

After committing and before pushing a feature branch:

1. Fetch and prune the remote refs again.
2. Apply the same clean-tree, lifecycle, linear-history, remote-divergence, and
   `origin/dev` ancestry checks used when resuming work.
3. Rebase onto `origin/dev` only when necessary.
4. Rerun validation affected by the rebase.
5. Read the gate's `push_mode`, `push_expected_sha`, and `push_command`. After
   explicit push authorization, execute only that exact command:
   - `create-only` uses an empty expected lease and fails if the branch appeared
     after the fetch;
   - `fast-forward` uses a normal explicit refspec;
   - `force-with-lease` binds the lease to the fetched remote feature SHA after
     a required rebase; and
   - `up-to-date` has no push command.

`not-ready` is emitted only for a newly created branch with no task commit and
also has no push command. `adopt-remote` has no push command either; see
[Rewrites and server-side rebases](#rewrites-and-server-side-rebases).

If the lease fails, fetch again and stop for review. Do not overwrite the
newer remote state.

Use `--json` when another tool consumes the result. Text and JSON output expose
the same stable fields; no caller should reconstruct a broader push command.

### Rewrites and server-side rebases

The gate refuses to replace a remote feature branch that is not an ancestor of
local HEAD. Two legitimate cases have explicit paths:

- A deliberate rewrite of the task's own published history, such as collapsing
  the branch into one integration commit or resuming after a rebase whose push
  was interrupted. Record the remote feature SHA observed before the rewrite and
  rerun the gate with `--expect-remote-sha <sha>`; the emitted
  `force-with-lease` is bound to that SHA.
- A rebase performed on the server, such as GitHub's "Update branch". When the
  remote carries exactly the local patches on the newer `origin/dev`, the gate
  reports `action=adopt-remote` and an `adopt_command`; run it and rerun the gate.

Remote commits whose content is absent locally are another owner's work and
always stop the gate.

## Push Authorization

Every push requires authorization from the task owner. A request that starts a
delivery workflow, such as "finish and deliver this feature", authorizes the
gate-emitted pushes, pull request creation, and component pull request
rebase-merges that the workflow performs for that task. It never authorizes:

- merging the x-farmer-dev root pull request, which only the platform owner
  performs;
- pushing to `dev` or `main` directly;
- a push command that the gate did not emit, including any `--force` or
  unscoped lease; or
- skipping Git hooks with `--no-verify`.

## Multi-Repository Order

The root repository and every subproject are separate Git working trees, so
this standard applies to each one independently. When this repository is used
inside the x-farmer-dev monorepo, multi-repository changes additionally follow
the root `docs/standards/platform-change-protocol.md`, which defines the
component-first commit and pull request order, gitlink conflict resolution, and
the final root integration commit.

A root rebase does not update a subproject branch, and a subproject rebase can
change the commit SHA pinned by the root. Reconcile gitlinks after any
subproject history rewrite.

## GitHub Merge Gate

Agent-side synchronization and local guards are preventive. The intended
merge-time enforcement for `dev` is:

- require pull requests and required status checks;
- require the pull request branch to be up to date with `dev` before merge;
- prohibit direct pushes and force pushes to `dev`, including normal
  administrator workflows unless an explicit break-glass procedure applies;
- require linear history; and
- allow only rebase merges.

Current state: the organization's GitHub plan does not support branch
protection or rulesets for private repositories, so GitHub enforces none of the
pull request, status check, or push rules above. Repository settings do apply:
x-farmer-dev, core, dashboard, desktop, and xclient allow only rebase merges and
use `dev` as their default branch. Until rulesets are available, the platform owner's manual merge
of the root pull request is the final integration gate, and the local guards
described in `skills/guard-git-operations/SKILL.md` are the only automated
enforcement on developer machines.

When concurrent pull-request volume makes repeated author-side rebases costly,
prefer a GitHub merge queue. Before enabling it, every required GitHub Actions
workflow must handle the `merge_group` event so the queued revision receives
the same required checks.

Git ancestry cannot prove that a pull request was squash- or rebase-merged
because those merge methods replace commit identities. Pull request state
remains authoritative for that lifecycle; a branch associated with a merged or
closed pull request must be treated as completed even if its tip is not an
ancestor of `origin/dev`.
