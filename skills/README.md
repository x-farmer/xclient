# XClient Agent Skills

This document directs AI agents to the skills available for the XClient project.
All paths in this document are relative to the XClient project root.

A skill is a task-specific operating guide. Read a skill only when the current
task matches its purpose. Skills do not replace the XClient `agent.md` or the
required reading it points to; always satisfy those reading requirements first,
then consult the relevant skill.

## Where to Find Skills

XClient project skills live in:

- `skills/`

Each skill is either a standalone Markdown file in that directory or a folder
containing a `SKILL.md` (plus optional `scripts/` resources). When a task matches
a skill's purpose, open the matching file and follow its instructions.

If no skill in the index below matches the task, fall back to the regular
XClient documentation referenced from `agent.md`.

## Skill Index

| Skill | Path | When to Use |
| --- | --- | --- |
| Build XClient OCI Image | `skills/build-image/SKILL.md` | Building, rebuilding, tagging, or pushing the XClient OCI image (`ghcr.io/x-farmer/xclient`) with the git-derived tag rule. |

## Adding a New Skill

When introducing a new skill for the XClient project:

1. Create a new Markdown file under `skills/` with a descriptive, action-
   oriented filename (for example `run-dev-container.md`). If the skill ships
   helper scripts or other resources, create a folder named after the skill
   containing a `SKILL.md` instead (for example `build-image/SKILL.md`).
2. Use a clear, action-oriented title inside the file that matches the
   filename's intent.
3. Open the file with a short "When to Use This Skill" section so agents can
   quickly decide whether the skill applies.
4. Keep all paths inside the skill relative to the XClient project root.
5. Add a row to the Skill Index above with the skill title, its path under
   `skills/`, and a one-sentence "When to Use" description.
