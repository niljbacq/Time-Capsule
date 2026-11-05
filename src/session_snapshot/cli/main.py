"""sessionctl — the Linux Session Snapshot command-line interface.

Every subcommand is a thin adapter over SessionService. No business logic
lives here; parsing, dispatch, and formatting only. This round provides
the read-only half (list, show, adapters, doctor, report stub). Mutation
commands (save, preview, restore, delete, rename, duplicate) land next.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from session_snapshot import __version__
from session_snapshot.cli import format as fmt
from session_snapshot.services.factory import create_default_service
from session_snapshot.services.session_service import SessionService
from session_snapshot.store.manifests import ManifestError

# Patchable by tests. Production uses create_default_service.
SERVICE_FACTORY: Callable[..., SessionService] = create_default_service


def _make_service(args: argparse.Namespace) -> SessionService:
    root = getattr(args, "store_root", None)
    return SERVICE_FACTORY(Path(root) if root else None)


def _dump_json(value: Any) -> str:
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json(indent=2)
    if isinstance(value, list):
        return json.dumps(
            [v.model_dump() if hasattr(v, "model_dump") else v for v in value],
            indent=2,
            default=str,
        )
    return json.dumps(value, indent=2, default=str)


def _emit(text: str) -> None:
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def _cmd_list(args: argparse.Namespace) -> int:
    result = _make_service(args).list_sessions()
    _emit(_dump_json(result) if args.json else fmt.format_session_list(result))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    manifest = _make_service(args).get_session(args.session_id)
    _emit(_dump_json(manifest) if args.json else fmt.format_manifest(manifest))
    return 0


def _cmd_adapters(args: argparse.Namespace) -> int:
    infos = _make_service(args).adapters()
    _emit(_dump_json(infos) if args.json else fmt.format_adapters(infos))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    sys.stderr.write(
        "error: report persistence is planned for a later phase; no "
        "operation history is stored yet.\n"
    )
    return 2


def _cmd_doctor(args: argparse.Namespace) -> int:
    _emit(fmt.format_doctor(_make_service(args)))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sessionctl",
        description="Cooperative Linux desktop session manager.",
    )
    parser.add_argument(
        "--version", action="version", version=f"sessionctl {__version__}"
    )
    parser.add_argument(
        "--store-root",
        default=None,
        help="override session directory (for testing)",
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("list", help="list saved sessions")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=_cmd_list)

    p = sub.add_parser("show", help="show one session manifest")
    p.add_argument("session_id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=_cmd_show)

    p = sub.add_parser("adapters", help="list installed adapters")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=_cmd_adapters)

    p = sub.add_parser("report", help="show operation reports (planned)")
    p.add_argument("target", nargs="?", default="latest")
    p.set_defaults(handler=_cmd_report)

    p = sub.add_parser("doctor", help="print diagnostic information")
    p.set_defaults(handler=_cmd_doctor)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        return handler(args)
    except ManifestError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
