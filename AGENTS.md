# XClient Agent Guide

This file is the canonical entry point for AI agents working in the xclient
codebase. All paths are relative to the xclient project root, so this harness
works both as a standalone clone and as `src/xclient` inside x-farmer-dev. When
a parent x-farmer-dev `AGENTS.md` exists, follow it in addition to this guide.

## Required XClient Reading

Before planning, reviewing, or explaining xclient work, read:

1. `docs/standards/architecture.md` — understand the xclient Clean Architecture boundaries.

Before adding or modifying any code, read:

1. `docs/standards/architecture.md` — understand that xclient uses Clean Architecture as its design principle.
2. `docs/standards/python-style.md` — follow Python naming, docstrings, type annotations, exceptions, CLI, and testing rules.
3. `docs/standards/comment-content-rule.md` — apply the shared comment-content gate.

## Coding Style Completion Gate

For any Python, CLI, adapter, infrastructure, test, or xclient support code
addition or modification, `docs/standards/python-style.md` is not just
background reading. It is a mandatory completion gate.

Before claiming that xclient work is done, agents must perform a manual
coding-style review of every changed xclient source file. Passing formatters,
linters, type checkers, tests, or IDE diagnostics is not sufficient.

The review must specifically verify high-maintenance documentation, typing,
error-handling, and CLI quality:

1. Every new or changed public module, class, exception, function, protocol,
   constant, adapter, command, or application boundary has a docstring that
   explains contract, boundary, caller obligations, error semantics, resource
   lifecycle, security, or compatibility where relevant.
2. Important internal boundaries also have valuable comments or docstrings. This
   includes use cases, ports, CLI command adapters, config loaders, HTTP/API
   adapters, credential handling, token handling, stream handling, and
   cross-component integration points.
3. Docstrings or comments that only restate an identifier, type, or obvious code
   behavior are treated as missing documentation and must be rewritten before
   continuing.
4. Code involving API tokens, credentials, config files, request IDs, streaming,
   retry behavior, timeout behavior, cancellation, terminal output, subprocesses,
   or resource cleanup must document the safety assumptions and maintenance
   constraints.
5. Changed CLI behavior must preserve clear stdout/stderr boundaries, stable
   exit-code semantics, actionable user-facing errors, and real API behavior.

If any changed xclient source file fails this documentation, typing,
error-handling, or CLI gate, the task is not complete. Fix the issue immediately
before moving to the next milestone, to-do item, or final response.

For large implementations that add or change multiple xclient modules, agents
must do a dedicated final docstring/type/CLI pass after the functional code
works. The final response must not describe the task as complete unless this
pass has been performed.

## API Consumption

XClient consumes APIs owned by provider components. When the task creates,
modifies, consumes, or validates backend API integration, use the provider
component's API contract as the source of truth.

XClient must not infer OpenAI-compatible API behavior from provider
implementation details.

If the provider contract is unavailable in a standalone clone, stop and obtain
the contract or use the x-farmer-dev integration checkout.

## Plans, Commits, Skills, And Harness Changes

- Run `skills/validate/scripts/validate.sh` before committing XClient changes;
  use `--install` in a fresh checkout.
- A standalone XClient validation proves only that component revision. Platform
  completion requires an x-farmer-dev root revision that pins this commit and
  passes root platform CI.
- Store active plan drafts under `docs/plans/manuscripts/` using
  `YYYYMMDD-<short-topic>.md`.
- Follow `docs/standards/conventional-commits.md` for commit messages.
- Discover canonical task workflows through `skills/README.md`.
- Before changing agent instructions, standards, or adapters, read
  `docs/standards/ai-development-harness.md`.
