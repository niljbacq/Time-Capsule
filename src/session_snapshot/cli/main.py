import argparse
import sys

from session_snapshot import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sessionctl")
    parser.add_argument("--version", action="version",
                        version=f"sessionctl {__version__}")
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())