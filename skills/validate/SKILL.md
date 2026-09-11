---
name: validate
description: Validate XClient dependency lock and tests. Use before committing XClient changes or when CI validates an XClient revision.
disable-model-invocation: true
---

# Validate XClient

Run from the XClient repository root:

```bash
skills/validate/scripts/validate.sh
skills/validate/scripts/validate.sh --install
```

`--install` performs a frozen dependency sync before pytest. Passing this skill
proves the XClient revision only; the root platform test uses XClient as its
request-path driver and owns integrated completion.
