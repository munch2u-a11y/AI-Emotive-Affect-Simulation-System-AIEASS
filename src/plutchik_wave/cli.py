"""Command-line and JSONL sidecar interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .runtime import AffectRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aieass")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command")

    jsonl = subparsers.add_parser(
        "jsonl", help="serve newline-delimited JSON on stdin/stdout"
    )
    jsonl.add_argument("--state-dir", type=Path)
    jsonl.add_argument("--no-autosave", action="store_true")

    demo = subparsers.add_parser("demo", help="run a small deterministic example")
    demo.add_argument("--state-dir", type=Path)
    return parser


def jsonl_server(runtime: AffectRuntime) -> int:
    """Run the sidecar protocol. Stdout contains JSON responses only."""
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        request_id: object = None
        try:
            message = json.loads(line)
            if not isinstance(message, dict):
                raise TypeError("Each input line must be a JSON object")
            request_id = message.get("id")
            response = runtime.process(message)
            if request_id is not None:
                response["id"] = request_id
        except Exception as exc:  # noqa: BLE001 - transport must isolate each request
            response = {
                "ok": False,
                "protocol_version": runtime.protocol_version,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
            if request_id is not None:
                response["id"] = request_id
        sys.stdout.write(
            json.dumps(response, separators=(",", ":"), sort_keys=True) + "\n"
        )
        sys.stdout.flush()
    return 0


def run_demo(state_dir: Path | None) -> int:
    runtime = AffectRuntime(state_dir=state_dir)
    events = [
        {
            "op": "step",
            "mode": "lagrangian",
            "session_id": "demo",
            "snapshot": {"omega": 0.8, "H": 0.2, "D_KL": 0.1, "T": 1.0, "s_total": 0.2},
            "anchor_ids": ["successful-plan"],
        },
        {
            "op": "step",
            "mode": "lagrangian",
            "session_id": "demo",
            "snapshot": {
                "omega": 0.82,
                "H": 0.15,
                "D_KL": 0.08,
                "T": 1.1,
                "s_total": 0.18,
            },
            "anchor_ids": ["successful-plan"],
        },
    ]
    for event in events:
        response = runtime.process(event)
        print(json.dumps(response, indent=2, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "jsonl":
        return jsonl_server(
            AffectRuntime(state_dir=args.state_dir, autosave=not args.no_autosave)
        )
    if args.command == "demo":
        return run_demo(args.state_dir)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
