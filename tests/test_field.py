from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from plutchik_wave import AffectConfig, PlutchikWaveSystem, PutchnikWaveSystem


class FieldTests(unittest.TestCase):
    def test_misspelling_alias_is_available(self) -> None:
        self.assertIs(PutchnikWaveSystem, PlutchikWaveSystem)

    def test_neutral_state(self) -> None:
        field = PlutchikWaveSystem()
        self.assertEqual(field.packet_count, 0)
        self.assertEqual(field.dominant_affect, "neutral")
        self.assertEqual(
            field.get_affect_values(),
            {
                "joy": 0.5,
                "trust": 0.5,
                "fear": 0.0,
                "surprise": 0.0,
                "sadness": 0.0,
                "disgust": 0.0,
                "anger": 0.0,
                "anticipation": 0.5,
            },
        )

    def test_corrected_gate_is_opt_in(self) -> None:
        legacy = PlutchikWaveSystem()
        corrected = PlutchikWaveSystem(config=AffectConfig.corrected_gate())
        self.assertIsNotNone(legacy.deposit_affect({}))
        self.assertIsNone(corrected.deposit_affect({}))

    def test_direct_deposit_and_memory_reactivation(self) -> None:
        field = PlutchikWaveSystem()
        values = {"joy": 1.0, "trust": 1.0, "anticipation": 0.8}
        field.deposit_affect(values, amplitude=1.0, anchor_ids=["m1"])
        field.deposit_affect(values, amplitude=1.0, anchor_ids=["m2"])
        result = field.sample(values, co_retrieved_memories=["m1", "m2"])
        self.assertGreaterEqual(result.reactivation_strength, 0.6)
        self.assertEqual(result.surfaced_memories, ("m1", "m2"))

    def test_max_packet_cap(self) -> None:
        field = PlutchikWaveSystem(config=AffectConfig(max_packets=2))
        for amplitude in (0.2, 0.8, 0.5):
            field.deposit_affect({"joy": 1.0}, amplitude=amplitude)
        self.assertEqual(field.packet_count, 2)
        self.assertEqual(
            sorted((packet.amplitude for packet in field.packets), reverse=True),
            [0.8, 0.5],
        )

    def test_rejects_nonfinite_input(self) -> None:
        field = PlutchikWaveSystem()
        with self.assertRaisesRegex(ValueError, "finite"):
            field.deposit_affect({"fear": float("nan")})

    def test_atomic_persistence_round_trip_and_helix_schema_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "nested" / "state.json"
            field = PlutchikWaveSystem(state_path=state_path)
            field.step_event("tool_success", anchor_ids=["memory-a"])
            field.save_state()
            restored = PlutchikWaveSystem(state_path=state_path, restore_state=True)
            self.assertEqual(restored.export_state(), field.export_state())

            data = json.loads(state_path.read_text(encoding="utf-8"))
            data["schema_version"] = "plutchik-8d-v1"
            restored.import_state(data)
            self.assertEqual(restored.packet_count, 1)


if __name__ == "__main__":
    unittest.main()
