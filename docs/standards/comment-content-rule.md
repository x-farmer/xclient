# Comment Content Rule

Comments must document information that code cannot reliably express. This
rule applies to source code, configuration, build files, and scripts.

A comment is allowed only when it records at least one of these categories:

- **Intent**: why the code exists.
- **Rationale**: why this approach was chosen.
- **Contract**: what callers or maintainers must guarantee.
- **Invariant**: what must always remain true.
- **Constraint**: what limitation shapes the implementation.
- **Risk**: what can break if the code changes incorrectly.
- **Side effect**: what state or external system is affected.
- **Domain mapping**: how implementation concepts map to platform concepts.
- **Operational context**: what matters for deployment, debugging, recovery,
  tracing, or observability.

Do not write comments that merely repeat code, translate identifiers, narrate
obvious control flow, describe syntax, preserve irrelevant history, or add
decorative section markers. Prefer a better name, type, test, or refactor when
it can express the same information.

Before adding or retaining a comment, verify:

1. Its semantic category is clear.
2. It prevents a plausible future mistake.
3. A comment is more appropriate than code or a test.
4. It remains true across normal implementation changes.

API documentation comments remain mandatory wherever the project language
standard requires them. They describe caller-facing contracts and are not
treated as prohibited narration.
