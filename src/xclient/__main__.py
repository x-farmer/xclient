"""Allows running xclient from source with `python -m xclient`."""

from xclient.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
