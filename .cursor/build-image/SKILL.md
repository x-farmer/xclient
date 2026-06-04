---
name: build-image
description: Build the x-farmer XClient OCI image (ghcr.io/x-farmer/xclient) with a git-derived tag, optionally pushing it. Use when the user runs /build-image or asks to build, rebuild, tag, or push the XClient image.
disable-model-invocation: true
---

# Build XClient OCI Image — Cursor Entry

This is the Cursor-specific entry point for the `build-image` skill. Its only
job is to wire the skill into Cursor's `/`-command discovery.

The full, IDE-neutral instructions and the helper script are defined once in:

`skills/build-image/SKILL.md` (relative to the XClient project root).

When this skill is invoked, read `skills/build-image/SKILL.md` and follow it
exactly. Do not duplicate or fork the steps here — keep this file as a thin
reference so there is a single source of truth.
