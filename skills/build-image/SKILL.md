# Build XClient OCI Image

Build the x-farmer XClient project's OCI image with a git-derived tag:

- `ghcr.io/x-farmer/xclient` — the thin OpenAI-compatible CLI client, shipped as
  a distroless Python 3.11 image (built from this project's `Dockerfile`).

XClient produces a single image (`xclient`); there is no target to choose. The
tag rule, registry/namespace flags, and `--push` behavior match the Core
`build-images` and Dashboard `build-image` skills so every x-farmer image shares
the same conventions.

This skill owns the helper script at
`skills/build-image/scripts/build-image.sh`. Run all commands from the XClient
project root (the directory holding this project's `Makefile` and `Dockerfile`).

## When to Use This Skill

Read this skill when the task asks to build, rebuild, or tag the XClient OCI
image (`xclient`), or to push it to the registry. This skill produces the
production OCI image; for local CLI development use the project's `uv`/`make`
workflow (`make install`, `make test`) instead.

## Invocation

```
/build-image [flags]
```

| Flag | Effect | Default |
| --- | --- | --- |
| `--tag <tag>` | Override the resolved image tag. | (tag rule) |
| `--registry <registry>` | Registry host in the image name. | `ghcr.io` |
| `--namespace <namespace>` | Namespace/org in the image name. | `x-farmer` |
| `--platform <list>` | Build for the given platform(s) via `docker buildx` (value passed straight through, e.g. `linux/amd64,linux/arm64`). | (host platform, plain `docker build`) |
| `--print-tag` | Print the resolved tag and exit without building. | — |
| `--push` | Push the image after a successful build. | — |
| `-h`, `--help` | Show script usage. | — |

## Image Name

The built image is named:

```
{registry}/{namespace}/xclient:{tag}
```

So with the defaults it is `ghcr.io/x-farmer/xclient:<tag>`. Override the prefix
with `--registry` and/or `--namespace` (for example `--registry
registry.example.com --namespace team` produces
`registry.example.com/team/xclient:<tag>`). The repository name is always
`xclient`.

## Tag Rule

The image tag is derived from git state. This rule is implemented in the XClient
`Makefile` (`make print-image-tag`), is the single source of truth, and matches
the Core and Dashboard images.

| Git state | Tag | Example |
| --- | --- | --- |
| Clean tree, HEAD is exactly at a git tag | the tag verbatim | `v1.2.3` |
| Clean tree, no tag at HEAD | `<branch>-<sha7>` | `dev-fd5663e` |
| Dirty tree (uncommitted changes) | `<branch>-<sha7>-<timestamp>` | `dev-fd5663e-20260603133000` |

Notes:

- "Clean" means `git status --porcelain` is empty (no modified tracked files and
  no untracked, non-ignored files). Any deviation counts as dirty.
- `<branch>` has any `/` normalized to `-` (docker tags forbid slashes).
- `<sha7>` is the 7-character short commit hash of `HEAD`.
- `<timestamp>` is the local `YYYYMMDDHHMMSS` build time. It is recomputed on
  every invocation, so a dirty build is **not** reproducible by tag: capture the
  tag printed at build time and deploy it explicitly.
- The resolved tag is baked into the image as `XCLIENT_VERSION` (the `VERSION`
  build arg) and the OCI `version` label, so logs, spans, and the image tag all
  agree on a single revision identifier.

## Multi-Arch Builds (`--platform`)

Without `--platform`, the build uses a plain `docker build` for the host
platform. When `--platform <list>` is given, the build switches to
`docker buildx build --platform <list>` and the value is forwarded to buildx
verbatim — pass a single platform (e.g. `linux/arm64`) or a comma-separated list
(e.g. `linux/amd64,linux/arm64`).

- A **single** platform without `--push` is loaded into the local docker image
  store (`--load`), so it appears in `docker images`.
- A **multi-platform** list builds a manifest that cannot be loaded locally, so
  it **requires `--push`** (the script fails fast with a clear message
  otherwise). With `--push`, buildx builds and pushes the multi-arch manifest in
  a single step.
- `--platform` builds require the Docker buildx plugin (`docker buildx`).

## Step 1 — Decide whether to push

Confirm before running. Use the AskQuestion tool when the request is ambiguous.

- **Push?**: build only (default) or also push to the registry (`--push`, which
  requires being logged in — `docker login <registry>`, e.g.
  `docker login ghcr.io`).

For reproducible release tags, commit (and ideally tag) the code first. If the
tree is dirty, the build still succeeds but the tag carries a timestamp.

## Step 2 — Preview the tag (optional)

```bash
skills/build-image/scripts/build-image.sh --print-tag
```

Use this to see exactly what tag the build will use before committing to it.

## Step 3 — Build

```bash
# Build the image with the resolved tag
skills/build-image/scripts/build-image.sh

# Build and push
skills/build-image/scripts/build-image.sh --push

# Pin an explicit tag (e.g. to match a known dirty build)
skills/build-image/scripts/build-image.sh --tag dev-fd5663e-20260603133000

# Build a single non-host platform and load it locally
skills/build-image/scripts/build-image.sh --platform linux/arm64

# Build a multi-arch manifest and push it (multi-platform requires --push)
skills/build-image/scripts/build-image.sh --platform linux/amd64,linux/arm64 --push

# Use a different registry / namespace
skills/build-image/scripts/build-image.sh --registry registry.example.com --namespace team
```

The script resolves the tag (via the Makefile rule unless `--tag` is given),
builds the image with `make build-docker` (plain `docker build`, or
`docker buildx build --platform …` when `--platform` is given), optionally
pushes, and prints the final image reference.

## Step 4 — Verify

- The script prints `Built image:` with the full
  `{registry}/{namespace}/xclient:<tag>` reference. Confirm it matches
  expectations.
- `docker images {registry}/{namespace}/xclient` lists the new tag (e.g.
  `docker images ghcr.io/x-farmer/xclient` with defaults).
- Smoke-test the entrypoint: `docker run --rm {ref} --help` prints the CLI help.
- For a multi-platform `--platform … --push` build the manifest is pushed
  straight to the registry and is **not** loaded locally, so `docker images`
  will not show it; inspect it with
  `docker buildx imagetools inspect {ref}` instead.

## Notes

- The tag value is exposed inside the image via `XCLIENT_VERSION` and the OCI
  labels, so the running container reports the revision it was built from.
- `--tag` overrides the rule everywhere for that build, including the in-image
  version stamp.
- Requires Docker Engine, `make`, and `git` on the building host (the `uv`-based
  dependency install happens inside the build container, so no host `uv` is
  needed). `--push` additionally requires registry credentials
  (`docker login <registry>`, e.g. `docker login ghcr.io`).
- `--platform` additionally requires the Docker buildx plugin
  (`docker buildx`). The plain (no `--platform`) path uses only `docker build`.
