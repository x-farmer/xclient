# AI Development Harness Standard

This repository provides one set of development rules to Cursor, Claude Code,
Codex, and other Agent Skills-compatible tools. The repository must remain
self-contained: cloning it without a parent checkout must leave every local
instruction, standard, and skill reference usable.

## Canonical content

- `AGENTS.md` is the canonical instruction entry point.
- Normative development rules live in `docs/standards/`.
- Task workflows live in `skills/<name>/SKILL.md`.
- Plan manuscripts live in `docs/plans/manuscripts/`.

Do not place operational rules in a tool adapter. Update canonical content
first, then regenerate or update the adapters.

## Tool adapters

- `CLAUDE.md` contains only `@AGENTS.md`.
- `.cursor/rules/agents-md.mdc` is an always-applied pointer to `AGENTS.md`.
- `.agents/skills/<name>/SKILL.md` exposes a canonical skill to Codex and
  Cursor.
- `.claude/skills/<name>/SKILL.md` exposes the same canonical skill to Claude
  Code.

Skill adapters copy only the canonical skill's discovery metadata and direct
the tool to read `skills/<name>/SKILL.md`. They must never copy the operational
procedure.

## Monorepo and standalone behavior

When this repository is a subproject inside `x-farmer-dev`, the monorepo's root
`AGENTS.md` applies platform and cross-project rules before this repository's
local guide. When cloned alone, the local `AGENTS.md` and local standards are
complete and must not require files above the repository root.

Shared quality-baseline files may be synchronized from `x-farmer-dev`, but the
committed copies in a subproject are authoritative and usable in a standalone
clone.

## Maintenance gate

Harness changes are incomplete until all entry-point links resolve, every
canonical skill has valid `name` and `description` frontmatter, adapters match
that metadata, and the synchronization check reports no legacy entry point,
standards location, or Cursor-only skill adapter.
