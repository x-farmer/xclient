#!/usr/bin/env bash

set -euo pipefail

install=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) install=1 ;;
    -h|--help)
      echo "usage: skills/validate/scripts/validate.sh [--install]"
      exit 0
      ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

if [[ "$install" == "1" ]]; then
  uv sync --frozen
fi

uv run pytest
