"""Optional MCP 2.x server for Codex, Claude Code, Hermes, OpenClaw, and Pi."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from .runtime import AffectRuntime


def build_server(runtime: AffectRuntime):
    try:
        from mcp.server import MCPServer
    except ImportError as exc:  # pragma: no cover - exercised by an install smoke test
        raise RuntimeError(
            "MCP support is optional. Install it with: pip install 'aieass[mcp]'"
        ) from exc

    server = MCPServer(
        "aieass",
        title="AIEASS — AI Emotive Affect Simulation System",
        description="Agent-agnostic computational affect control field extracted from Helix-AGI.",
        instructions=(
            "Use affect_step_lagrangian when the host has Helix-style numerical metrics, or "
            "affect_step_direct for an explicit 8D control vector. Call once per meaningful agent "
            "cycle, then treat the returned context as a soft attention/tone prior only. The values "
            "are computational control state, not evidence of subjective feelings."
        ),
        version="0.1.0",
    )

    @server.tool()
    def affect_step_lagrangian(
        session_id: str = "default",
        omega: float = 0.5,
        H: float = 0.0,
        D_KL: float = 0.0,
        T: float = 1.0,
        s_total: float = 0.0,
        anchor_ids: list[str] | None = None,
        stagnation_counter: int = 0,
    ) -> dict[str, object]:
        """Advance one cycle from Helix metrics and return steering/context/events."""
        return runtime.process(
            {
                "op": "step",
                "mode": "lagrangian",
                "session_id": session_id,
                "snapshot": {
                    "omega": omega,
                    "H": H,
                    "D_KL": D_KL,
                    "T": T,
                    "s_total": s_total,
                },
                "anchor_ids": anchor_ids or [],
                "stagnation_counter": stagnation_counter,
            }
        )

    @server.tool()
    def affect_step_direct(
        session_id: str = "default",
        joy: float = 0.5,
        trust: float = 0.5,
        fear: float = 0.0,
        surprise: float = 0.0,
        sadness: float = 0.0,
        disgust: float = 0.0,
        anger: float = 0.0,
        anticipation: float = 0.5,
        amplitude: float | None = None,
        anchor_ids: list[str] | None = None,
    ) -> dict[str, object]:
        """Advance one cycle from an explicit Plutchik control vector."""
        return runtime.process(
            {
                "op": "step",
                "mode": "affect",
                "session_id": session_id,
                "affect": {
                    "joy": joy,
                    "trust": trust,
                    "fear": fear,
                    "surprise": surprise,
                    "sadness": sadness,
                    "disgust": disgust,
                    "anger": anger,
                    "anticipation": anticipation,
                },
                "amplitude": amplitude,
                "anchor_ids": anchor_ids or [],
            }
        )

    @server.tool()
    def affect_get_state(session_id: str = "default") -> dict[str, object]:
        """Read the current affect summary without changing it."""
        return runtime.process({"op": "state", "session_id": session_id})

    @server.tool()
    def affect_step_event(
        event: str,
        session_id: str = "default",
        magnitude: float = 1.0,
        anchor_ids: list[str] | None = None,
    ) -> dict[str, object]:
        """Advance from a portable event such as tool_success, blocked, novelty, or risk_detected."""
        return runtime.process(
            {
                "op": "step",
                "mode": "event",
                "event": event,
                "session_id": session_id,
                "magnitude": magnitude,
                "anchor_ids": anchor_ids or [],
            }
        )

    @server.tool()
    def affect_get_context(session_id: str = "default") -> dict[str, object]:
        """Read a compact prompt overlay and interference sample."""
        return runtime.process({"op": "context", "session_id": session_id})

    @server.tool()
    def affect_reset(session_id: str = "default") -> dict[str, object]:
        """Reset one session to its neutral initial state."""
        return runtime.process({"op": "reset", "session_id": session_id})

    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aieass-mcp")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=os.environ.get("PLUTCHIK_WAVE_STATE_DIR"),
        help="optional directory for per-session durable state",
    )
    parser.add_argument(
        "--transport", choices=("stdio", "streamable-http"), default="stdio"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    server = build_server(AffectRuntime(state_dir=args.state_dir))
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
