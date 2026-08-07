"""Serializable public value objects."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from .config import PRIMARIES, AffectConfig


def finite_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a finite number, not bool")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def affect_vector(
    values: Mapping[str, object] | Sequence[object],
    config: AffectConfig,
) -> list[float]:
    """Normalize a named or positional affect value into a clamped 8D vector."""
    if isinstance(values, Mapping):
        unknown = set(values) - set(config.primaries)
        if unknown:
            raise ValueError(f"Unknown affect dimensions: {', '.join(sorted(unknown))}")
        return [
            clamp(finite_float(values.get(name, config.neutral_baselines[name]), name))
            for name in config.primaries
        ]
    if isinstance(values, (str, bytes)):
        raise TypeError("Affect values must be a mapping or numeric sequence")
    items = list(values)
    if len(items) != config.dimensions:
        raise ValueError(
            f"Expected {config.dimensions} affect values, received {len(items)}"
        )
    return [
        clamp(finite_float(value, config.primaries[index]))
        for index, value in enumerate(items)
    ]


@dataclass
class WavePacket:
    """A single emotional trace in 8D Plutchik affect space."""

    position: list[float]
    initial_amplitude: float
    deposit_pulse: int
    anchor_memories: set[str] = field(default_factory=set)
    blended_memories: dict[str, float] = field(default_factory=dict)
    sigma: list[float] = field(default_factory=list)
    amplitude: float | None = None

    def prepare(self, config: AffectConfig) -> None:
        self.position = affect_vector(self.position, config)
        if not self.sigma:
            self.sigma = [config.initial_sigma] * config.dimensions
        if len(self.sigma) != config.dimensions:
            raise ValueError(f"Expected {config.dimensions} sigma values")
        self.sigma = [max(0.001, finite_float(v, "sigma")) for v in self.sigma]
        self.initial_amplitude = max(
            0.0, finite_float(self.initial_amplitude, "initial_amplitude")
        )
        self.amplitude = (
            self.initial_amplitude
            if self.amplitude is None
            else max(0.0, finite_float(self.amplitude, "amplitude"))
        )
        self.deposit_pulse = int(self.deposit_pulse)
        self.anchor_memories = {str(item) for item in self.anchor_memories}
        self.blended_memories = {
            str(key): finite_float(value, "blended memory strength")
            for key, value in self.blended_memories.items()
        }

    def intensity(self, config: AffectConfig) -> float:
        deviations = [
            abs(self.position[i] - config.neutral_baselines[name])
            for i, name in enumerate(config.primaries)
        ]
        return sum(deviations) / config.dimensions * 2.0

    def importance(self, config: AffectConfig) -> float:
        return min(1.0, len(self.anchor_memories) / config.importance_maturity)

    def current_phase(self, pulse: int, config: AffectConfig) -> float:
        elapsed = pulse - self.deposit_pulse
        return (elapsed * config.composite_frequency) % (2.0 * math.pi)

    def evolve(self, config: AffectConfig) -> None:
        for i, name in enumerate(config.primaries):
            self.sigma[i] += config.diffusion_rates[name]
        intensity_mult = 1.0 + self.intensity(config)
        importance_mult = 1.0 + self.importance(config) * config.importance_bonus_max
        effective_halflife = config.base_halflife * intensity_mult * importance_mult
        decay_factor = 0.5 ** (1.0 / effective_halflife)
        self.amplitude = max(0.0, float(self.amplitude) * decay_factor)

    def spatial_contribution(
        self, sample_position: Sequence[float], config: AffectConfig
    ) -> float:
        weighted_sq_dist = 0.0
        for i in range(config.dimensions):
            sigma = max(self.sigma[i], 0.001)
            weighted_sq_dist += ((sample_position[i] - self.position[i]) / sigma) ** 2
        return float(self.amplitude) * math.exp(-0.5 * weighted_sq_dist)

    def is_alive(self, config: AffectConfig) -> bool:
        return float(self.amplitude) >= config.prune_threshold

    def to_dict(self) -> dict[str, object]:
        return {
            "position": list(self.position),
            "initial_amplitude": self.initial_amplitude,
            "deposit_pulse": self.deposit_pulse,
            "anchor_memories": sorted(self.anchor_memories),
            "blended_memories": [
                [key, self.blended_memories[key]]
                for key in sorted(self.blended_memories)
            ],
            "sigma": list(self.sigma),
            "amplitude": self.amplitude,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object], config: AffectConfig) -> WavePacket:
        blended = data.get("blended_memories", [])
        if isinstance(blended, Mapping):
            blended_map = dict(blended)
        else:
            blended_map = {str(item[0]): item[1] for item in blended}  # type: ignore[index]
        packet = cls(
            position=list(data["position"]),  # type: ignore[arg-type]
            initial_amplitude=finite_float(
                data["initial_amplitude"], "initial_amplitude"
            ),
            deposit_pulse=int(data["deposit_pulse"]),
            anchor_memories=set(data.get("anchor_memories", [])),  # type: ignore[arg-type]
            blended_memories=blended_map,
            sigma=list(data.get("sigma", [])),  # type: ignore[arg-type]
            amplitude=data.get("amplitude"),  # type: ignore[arg-type]
        )
        packet.prepare(config)
        return packet


@dataclass(frozen=True)
class AffectResult:
    """Result of phase-coherent sampling."""

    field_intensity: float = 0.0
    contributing_packets: int = 0
    steering_vector: tuple[float, ...] = (0.0,) * 8
    surfaced_memories: tuple[str, ...] = ()
    reactivation_strength: float = 0.0
    dominant_affect: str = "neutral"
    cognitive_diversity_signal: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "field_intensity": self.field_intensity,
            "contributing_packets": self.contributing_packets,
            "steering_vector": list(self.steering_vector),
            "surfaced_memories": list(self.surfaced_memories),
            "reactivation_strength": self.reactivation_strength,
            "dominant_affect": self.dominant_affect,
            "cognitive_diversity_signal": self.cognitive_diversity_signal,
        }

    def steering_values(self) -> dict[str, float]:
        return dict(zip(PRIMARIES, self.steering_vector))


def memory_ids(values: Iterable[object] | None) -> list[str]:
    if values is None:
        return []
    return [str(value) for value in values]
