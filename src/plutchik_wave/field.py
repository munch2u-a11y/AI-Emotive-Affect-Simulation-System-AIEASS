"""Dependency-free affect field engine.

This is a behavior-preserving extraction of Helix-AGI's ``affect_field``
with configuration, validation, locking, direct affect input, and atomic state
persistence added at the package boundary.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from .config import AffectConfig
from .events import event_vector
from .models import (
    AffectResult,
    WavePacket,
    affect_vector,
    clamp,
    finite_float,
    memory_ids,
)


class PlutchikWaveSystem:
    """Stateful 8D Plutchik wave-packet field.

    One instance represents one agent/session. The object is safe to call from
    multiple threads. It performs no model, network, telemetry, or background
    activity.
    """

    schema_version = "plutchik-wave-v1"
    helix_schema_version = "plutchik-8d-v1"

    def __init__(
        self,
        *,
        config: AffectConfig | None = None,
        state_path: str | os.PathLike[str] | None = None,
        restore_state: bool = False,
    ) -> None:
        self.config = config or AffectConfig()
        self.state_path = Path(state_path) if state_path is not None else None
        self.packets: list[WavePacket] = []
        self.current_pulse = 0
        self._prev_s_total = 0.0
        self._prev_omega = 0.5
        self._stagnation_counter = 0
        self._summary_cache: dict[str, float | str] | None = None
        self._summary_cache_pulse = -1
        self._lock = threading.RLock()
        if restore_state:
            self.load_state()

    def _invalidate(self) -> None:
        self._summary_cache = None
        self._summary_cache_pulse = -1

    def _position_intensity(self, position: Sequence[float]) -> float:
        deviations = [
            abs(position[i] - self.config.neutral_baselines[name])
            for i, name in enumerate(self.config.primaries)
        ]
        return sum(deviations) / self.config.dimensions * 2.0

    def _deposit_amplitude(self, raw_intensity: float) -> float | None:
        cfg = self.config
        if cfg.helix_legacy_floor_before_gate:
            amplitude = max(cfg.deposit_amplitude_floor, raw_intensity)
            return None if amplitude < cfg.min_deposit_intensity else amplitude
        if raw_intensity < cfg.min_deposit_intensity:
            return None
        return max(cfg.deposit_amplitude_floor, raw_intensity)

    def map_lagrangian(
        self,
        snapshot: Mapping[str, object],
        *,
        stagnation_counter: int | None = None,
    ) -> list[float]:
        """Map Helix Lagrangian metrics into the canonical Plutchik vector.

        Recognized metrics are ``omega``, ``H``, ``D_KL``, ``T``, and
        ``s_total``. Missing values retain the Helix defaults.
        """
        with self._lock:
            if stagnation_counter is None:
                stagnation = self._stagnation_counter
            else:
                stagnation = max(0, int(stagnation_counter))

            omega = finite_float(snapshot.get("omega", 0.5), "omega")
            entropy = finite_float(snapshot.get("H", 0.0), "H")
            divergence = finite_float(snapshot.get("D_KL", 0.0), "D_KL")
            temperature = finite_float(snapshot.get("T", 1.0), "T")
            s_total = finite_float(snapshot.get("s_total", 0.0), "s_total")

            if self.current_pulse == 0 or self._prev_s_total == 0.0:
                delta_s = 0.0
                omega_velocity = 0.0
            else:
                delta_s = s_total - self._prev_s_total
                omega_velocity = omega - self._prev_omega

            joy = omega
            trust = 1.0 - divergence
            fear = max(0.0, delta_s - omega_velocity) * 5.0
            surprise = abs(delta_s) * 5.0
            sadness = max(0.0, -omega_velocity) * 10.0
            disgust = stagnation / 10.0
            anger = math.log1p(max(-0.999999999, entropy)) * (1.0 - omega) * 0.8
            anticipation = max(0.0, omega_velocity) * 10.0

            fear += entropy * (1.0 - omega) * 0.3
            if divergence > 0:
                anticipation += divergence * 0.5
                if divergence > 1.5:
                    fear += (divergence - 1.5) * (1.0 - omega) * 0.3
            if temperature > 1.0:
                excess_temperature = temperature - 1.0
                surprise += excess_temperature * 0.3
                anticipation += excess_temperature * 0.2

            return [
                clamp(joy),
                clamp(trust),
                clamp(fear),
                clamp(surprise),
                clamp(sadness),
                clamp(disgust),
                clamp(anger),
                clamp(anticipation),
            ]

    def _append_packet(
        self,
        position: list[float],
        amplitude: float,
        anchor_ids: Iterable[object] | None,
    ) -> WavePacket:
        packet = WavePacket(
            position=position,
            initial_amplitude=amplitude,
            deposit_pulse=self.current_pulse,
            anchor_memories=set(memory_ids(anchor_ids)),
        )
        packet.prepare(self.config)
        self.packets.append(packet)
        if len(self.packets) > self.config.max_packets:
            self.packets.sort(key=lambda item: float(item.amplitude), reverse=True)
            self.packets = self.packets[: self.config.max_packets]
        self._invalidate()
        return packet

    def deposit_lagrangian(
        self,
        snapshot: Mapping[str, object],
        *,
        anchor_ids: Iterable[object] | None = None,
        stagnation_counter: int = 0,
    ) -> WavePacket | None:
        """Deposit a packet from Helix-compatible numerical metrics."""
        with self._lock:
            self._stagnation_counter = max(0, int(stagnation_counter))
            position = self.map_lagrangian(snapshot)
            self._prev_s_total = finite_float(snapshot.get("s_total", 0.0), "s_total")
            self._prev_omega = finite_float(snapshot.get("omega", 0.5), "omega")
            amplitude = self._deposit_amplitude(self._position_intensity(position))
            if amplitude is None:
                return None
            return self._append_packet(position, amplitude, anchor_ids)

    def deposit_affect(
        self,
        values: Mapping[str, object] | Sequence[object],
        *,
        amplitude: float | None = None,
        anchor_ids: Iterable[object] | None = None,
    ) -> WavePacket | None:
        """Deposit an agent-native affect vector without Helix metrics."""
        with self._lock:
            position = affect_vector(values, self.config)
            if amplitude is None:
                packet_amplitude = self._deposit_amplitude(
                    self._position_intensity(position)
                )
            else:
                packet_amplitude = max(0.0, finite_float(amplitude, "amplitude"))
                if packet_amplitude < self.config.min_deposit_intensity:
                    return None
            if packet_amplitude is None:
                return None
            return self._append_packet(position, packet_amplitude, anchor_ids)

    def evolve(
        self,
        *,
        accessed_memory_ids: Iterable[object] | None = None,
        steps: int = 1,
    ) -> None:
        """Advance diffusion and decay by one or more agent cycles."""
        if steps < 0:
            raise ValueError("steps cannot be negative")
        accessed = memory_ids(accessed_memory_ids)
        with self._lock:
            for _ in range(steps):
                self.current_pulse += 1
                surviving: list[WavePacket] = []
                for packet in self.packets:
                    packet.evolve(self.config)
                    if (
                        accessed
                        and float(packet.amplitude)
                        >= self.config.blend_amplitude_threshold
                    ):
                        for memory_id in accessed:
                            packet.blended_memories[memory_id] = float(packet.amplitude)
                    if packet.is_alive(self.config):
                        surviving.append(packet)
                self.packets = surviving
            self._invalidate()

    def sample(
        self,
        affect_position: Mapping[str, object] | Sequence[object] | None = None,
        *,
        co_retrieved_memories: Iterable[object] | None = None,
    ) -> AffectResult:
        """Sample phase-coherent interference at an affect position."""
        with self._lock:
            if not self.packets:
                return AffectResult()
            if affect_position is None:
                summary = self._compute_summary()
                position = [float(summary[name]) for name in self.config.primaries]
            else:
                position = affect_vector(affect_position, self.config)

            contributions: list[tuple[WavePacket, float, float]] = []
            for packet in self.packets:
                spatial = packet.spatial_contribution(position, self.config)
                phase = packet.current_phase(self.current_pulse, self.config)
                contribution = spatial * math.cos(phase)
                contributions.append((packet, contribution, spatial))

            field_intensity = max(0.0, sum(item[1] for item in contributions))
            contributing = [
                packet for packet, contribution, _ in contributions if contribution > 0
            ]
            steering = self._steering_vector(contributions)
            reactivation_strength = 0.0
            surfaced_memories: list[str] = []
            retrieved = memory_ids(co_retrieved_memories)
            if field_intensity >= self.config.proximity_threshold and retrieved:
                overlap = self._semantic_overlap(contributing, retrieved)
                if overlap > 0:
                    reactivation_strength = field_intensity * overlap
                if reactivation_strength >= self.config.awareness_threshold:
                    surfaced_memories = sorted(
                        {
                            memory_id
                            for packet in contributing
                            for memory_id in (
                                packet.anchor_memories | set(packet.blended_memories)
                            )
                        }
                    )

            summary = self._compute_summary()
            return AffectResult(
                field_intensity=field_intensity,
                contributing_packets=len(contributing),
                steering_vector=tuple(steering),
                surfaced_memories=tuple(surfaced_memories),
                reactivation_strength=reactivation_strength,
                dominant_affect=str(summary["dominant"]),
                cognitive_diversity_signal=self._diversity_signal(summary),
            )

    def _steering_vector(
        self,
        contributions: Sequence[tuple[WavePacket, float, float]],
    ) -> list[float]:
        total_weight = sum(abs(spatial) for _, _, spatial in contributions)
        if total_weight == 0:
            return [0.0] * self.config.dimensions
        steering = [0.0] * self.config.dimensions
        for packet, _, spatial in contributions:
            weight = abs(spatial) / total_weight
            for index in range(self.config.dimensions):
                steering[index] += packet.position[index] * weight
        return steering

    @staticmethod
    def _semantic_overlap(
        contributing: Sequence[WavePacket], co_retrieved: Sequence[str]
    ) -> float:
        if len(contributing) < 2 or not co_retrieved:
            return 0.0
        co_set = set(co_retrieved)
        packets_with_overlap = sum(
            1
            for packet in contributing
            if not co_set.isdisjoint(
                packet.anchor_memories | set(packet.blended_memories)
            )
        )
        if packets_with_overlap >= 2:
            return packets_with_overlap / len(contributing)
        return 0.0

    def _compute_summary(self) -> dict[str, float | str]:
        if (
            self._summary_cache is not None
            and self._summary_cache_pulse == self.current_pulse
        ):
            return dict(self._summary_cache)
        if not self.packets:
            result: dict[str, float | str] = {
                name: self.config.neutral_baselines[name]
                for name in self.config.primaries
            }
            result.update(total_amplitude=0.0, dominant="neutral")
        else:
            total_amplitude = sum(float(packet.amplitude) for packet in self.packets)
            if total_amplitude == 0:
                result = {
                    name: self.config.neutral_baselines[name]
                    for name in self.config.primaries
                }
                result.update(total_amplitude=0.0, dominant="neutral")
            else:
                weighted = [0.0] * self.config.dimensions
                for packet in self.packets:
                    for index in range(self.config.dimensions):
                        weighted[index] += packet.position[index] * float(
                            packet.amplitude
                        )
                averages = [value / total_amplitude for value in weighted]
                result = {
                    name: averages[index]
                    for index, name in enumerate(self.config.primaries)
                }
                result["total_amplitude"] = total_amplitude
                max_deviation = 0.0
                dominant = "neutral"
                for index, name in enumerate(self.config.primaries):
                    deviation = abs(
                        averages[index] - self.config.neutral_baselines[name]
                    )
                    if (
                        deviation > max_deviation
                        and deviation > self.config.dominant_affect_threshold
                    ):
                        max_deviation = deviation
                        dominant = name
                result["dominant"] = dominant
        self._summary_cache = dict(result)
        self._summary_cache_pulse = self.current_pulse
        return result

    @staticmethod
    def _diversity_signal(summary: Mapping[str, float | str]) -> float:
        disgust = float(summary.get("disgust", 0.0))
        anticipation = float(summary.get("anticipation", 0.5))
        boredom = min(1.0, disgust * 2.0) if 0.1 <= disgust <= 0.5 else 0.0
        anticipation_factor = max(0.0, 1.0 - anticipation * 2.0)
        return min(1.0, boredom * (1.0 + anticipation_factor * 0.5))

    @property
    def packet_count(self) -> int:
        return len(self.packets)

    @property
    def dominant_affect(self) -> str:
        with self._lock:
            return str(self._compute_summary()["dominant"])

    @property
    def current_intensity(self) -> float:
        with self._lock:
            return float(self._compute_summary()["total_amplitude"])

    def get_affect_values(self, *, rounded: bool = True) -> dict[str, float]:
        with self._lock:
            summary = self._compute_summary()
            values = {name: float(summary[name]) for name in self.config.primaries}
            return (
                {name: round(value, 3) for name, value in values.items()}
                if rounded
                else values
            )

    def control_events(self, result: AffectResult) -> list[str]:
        """Translate sampling thresholds into framework-neutral event names."""
        events: list[str] = []
        if result.field_intensity >= self.config.resonance_intensity_threshold:
            events.append("affect_resonance")
        if result.cognitive_diversity_signal >= self.config.boredom_diversity_threshold:
            events.append("affect_boredom")
        if result.field_intensity >= self.config.high_intensity_threshold:
            events.append("affect_intensity_high")
        return events

    def render_context(self, result: AffectResult | None = None) -> str:
        """Render a compact, safe prompt overlay for an agent runtime."""
        with self._lock:
            result = result or self.sample()
            values = self.get_affect_values()
            active = sorted(values.items(), key=lambda item: item[1], reverse=True)[:3]
            top = ", ".join(f"{name}={value:.3f}" for name, value in active)
            return (
                "Affect control signal (computational state, not a claim of subjective feeling): "
                f"dominant={result.dominant_affect}; {top}; "
                f"diversity={result.cognitive_diversity_signal:.3f}. "
                "Use this only as a soft attention/tone prior; task instructions and safety rules take precedence."
            )

    def step_lagrangian(
        self,
        snapshot: Mapping[str, object],
        *,
        anchor_ids: Iterable[object] | None = None,
        stagnation_counter: int = 0,
    ) -> dict[str, object]:
        """Atomically run Helix's deposit -> evolve -> sample lifecycle."""
        with self._lock:
            anchors = memory_ids(anchor_ids)
            packet = self.deposit_lagrangian(
                snapshot,
                anchor_ids=anchors,
                stagnation_counter=stagnation_counter,
            )
            self.evolve(accessed_memory_ids=anchors)
            result = self.sample(co_retrieved_memories=anchors)
            return self._step_payload(packet, result)

    def step_affect(
        self,
        values: Mapping[str, object] | Sequence[object],
        *,
        amplitude: float | None = None,
        anchor_ids: Iterable[object] | None = None,
    ) -> dict[str, object]:
        """Atomically run a direct affect deposit -> evolve -> sample lifecycle."""
        with self._lock:
            anchors = memory_ids(anchor_ids)
            packet = self.deposit_affect(
                values, amplitude=amplitude, anchor_ids=anchors
            )
            self.evolve(accessed_memory_ids=anchors)
            result = self.sample(co_retrieved_memories=anchors)
            return self._step_payload(packet, result)

    def step_event(
        self,
        event: str,
        *,
        magnitude: float = 1.0,
        overrides: Mapping[str, object] | None = None,
        anchor_ids: Iterable[object] | None = None,
    ) -> dict[str, object]:
        """Advance one cycle from a portable operational event template."""
        values = event_vector(
            event,
            magnitude=magnitude,
            config=self.config,
            overrides=overrides,
        )
        return self.step_affect(values, anchor_ids=anchor_ids)

    def _step_payload(
        self, packet: WavePacket | None, result: AffectResult
    ) -> dict[str, object]:
        return {
            "packet_deposited": packet is not None,
            "result": result.to_dict(),
            "events": self.control_events(result),
            "context": self.render_context(result),
            "state": self.to_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema_version": self.schema_version,
                "current_pulse": self.current_pulse,
                "packet_count": self.packet_count,
                "dominant_affect": self.dominant_affect,
                "intensity": round(self.current_intensity, 3),
                "affect_values": self.get_affect_values(),
            }

    def export_state(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema_version": self.schema_version,
                "source_compatibility": "Helix-AGI@c599233",
                "current_pulse": self.current_pulse,
                "prev_s_total": self._prev_s_total,
                "prev_omega": self._prev_omega,
                "stagnation_counter": self._stagnation_counter,
                "packets": [packet.to_dict() for packet in self.packets],
            }

    def import_state(self, data: Mapping[str, object]) -> None:
        with self._lock:
            schema = data.get("schema_version", self.helix_schema_version)
            if schema not in {self.schema_version, self.helix_schema_version}:
                raise ValueError(f"Unsupported affect state schema: {schema}")
            packets = [
                WavePacket.from_dict(item, self.config)
                for item in data.get("packets", [])  # type: ignore[union-attr]
            ]
            self.current_pulse = max(0, int(data.get("current_pulse", 0)))
            self._prev_s_total = finite_float(
                data.get("prev_s_total", 0.0), "prev_s_total"
            )
            self._prev_omega = finite_float(data.get("prev_omega", 0.5), "prev_omega")
            self._stagnation_counter = max(0, int(data.get("stagnation_counter", 0)))
            self.packets = packets[: self.config.max_packets]
            self._invalidate()

    def save_state(self, path: str | os.PathLike[str] | None = None) -> Path:
        """Atomically persist state and return the resolved path."""
        target = Path(path) if path is not None else self.state_path
        if target is None:
            raise ValueError("No state path configured")
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.export_state(), indent=2, sort_keys=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        return target

    def load_state(self, path: str | os.PathLike[str] | None = None) -> bool:
        target = Path(path) if path is not None else self.state_path
        if target is None:
            raise ValueError("No state path configured")
        if not target.exists():
            return False
        with target.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, Mapping):
            raise TypeError("Affect state must be a JSON object")
        self.import_state(data)
        return True

    def reset(self, *, delete_saved_state: bool = False) -> None:
        with self._lock:
            self.packets = []
            self.current_pulse = 0
            self._prev_s_total = 0.0
            self._prev_omega = 0.5
            self._stagnation_counter = 0
            self._invalidate()
            if delete_saved_state and self.state_path is not None:
                try:
                    self.state_path.unlink()
                except FileNotFoundError:
                    pass
