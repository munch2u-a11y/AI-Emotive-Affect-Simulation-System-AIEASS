from __future__ import annotations

import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plutchik_wave import AffectRuntime
from plutchik_wave.cli import jsonl_server
from plutchik_wave.mcp_server import build_server


class RuntimeTests(unittest.TestCase):
    def test_event_mode_and_session_isolation(self) -> None:
        runtime = AffectRuntime()
        response = runtime.process(
            {
                "op": "step",
                "mode": "event",
                "event": "tool_success",
                "session_id": "agent-a",
                "anchor_ids": ["tool-call-1"],
            }
        )
        self.assertTrue(response["ok"])
        self.assertEqual(response["state"]["packet_count"], 1)
        untouched = runtime.process({"op": "state", "session_id": "agent-b"})
        self.assertEqual(untouched["state"]["packet_count"], 0)

    def test_jsonl_protocol_success_and_error(self) -> None:
        source = io.StringIO(
            json.dumps({"id": 1, "op": "step", "mode": "event", "event": "novelty"})
            + "\n"
            + json.dumps({"id": 2, "op": "unknown"})
            + "\n"
        )
        target = io.StringIO()
        with patch("sys.stdin", source), patch("sys.stdout", target):
            self.assertEqual(jsonl_server(AffectRuntime()), 0)
        responses = [json.loads(line) for line in target.getvalue().splitlines()]
        self.assertTrue(responses[0]["ok"])
        self.assertEqual(responses[0]["id"], 1)
        self.assertFalse(responses[1]["ok"])
        self.assertEqual(responses[1]["id"], 2)

    def test_autosave_rehydrates_across_runtime_instances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = AffectRuntime(state_dir=Path(directory))
            first.process(
                {
                    "op": "step",
                    "mode": "event",
                    "event": "progress",
                    "session_id": "a/b",
                }
            )
            second = AffectRuntime(state_dir=Path(directory))
            state = second.process({"op": "state", "session_id": "a/b"})
            self.assertEqual(state["state"]["packet_count"], 1)
            self.assertEqual(len(list(Path(directory).glob("session-*.json"))), 1)

    def test_mcp_server_exposes_expected_tools(self) -> None:
        server = build_server(AffectRuntime())
        tools = asyncio.run(server.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(
            names,
            {
                "affect_step_lagrangian",
                "affect_step_direct",
                "affect_step_event",
                "affect_get_state",
                "affect_get_context",
                "affect_reset",
            },
        )


if __name__ == "__main__":
    unittest.main()
