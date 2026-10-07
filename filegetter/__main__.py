#!/usr/bin/env python
"""The main entry point. Invoke as `filegetter` or `python -m filegetter`."""

import sys


def main():
    try:
        from .core import cli

        exit_status = cli()
    except KeyboardInterrupt:
        print("Interrupted. Aborting.", file=sys.stderr)
        sys.exit(130)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
