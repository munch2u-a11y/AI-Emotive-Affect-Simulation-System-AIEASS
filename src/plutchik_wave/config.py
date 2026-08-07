"""Configuration for the affect field.

Defaults reproduce Helix-AGI commit c599233 as closely as possible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field

PRIMARIES = (
    "joy",
    "trust",
    "fear",
    "surprise",
    "sadness",
    "disgust",
    "anger",
    "anticipation",
)


def _neutral() -> dict[str, float]:
    return {
        "joy": 0.5,
        "trust": 0.5,
        "fear": 0.0,
        "surprise": 0.0,
        "sadness": 0.0,
        "disgust": 0.0,
        "anger": 0.0,
        "anticipation": 0.5,
    }


def _diffusion() -> dict[str, float]:
    return {
        "joy": 0.016,
        "trust": 0.010,
        "fear": 0.12,
        "surprise": 0.16,
        "sadness": 0.016,
        "disgust": 0.06,
        "anger": 0.10,
        "anticipation": 0.02,
    }


def _frequencies() -> dict[str, float]:
    return {
        "joy": 0.04,
        "trust": 0.02,
        "fear": 0.10,
        "surprise": 0.12,
        "sadness": 0.03,
        "disgust": 0.05,
        "anger": 0.08,
        "anticipation": 0.04,
    }


@dataclass(frozen=True)
class AffectConfig:
    """All affect dynamics in one injectable configuration object.

    ``helix_legacy_floor_before_gate=True`` retains a Helix quirk: amplitude
    is floored to 0.1 before checking a 0.05 deposit threshold, so every
    valid event deposits a packet. Set it to ``False`` to make the gate
    effective while retaining every other default.
    """

    primaries: tuple[str, ...] = PRIMARIES
    neutral_baselines: Mapping[str, float] = field(default_factory=_neutral)
    diffusion_rates: Mapping[str, float] = field(default_factory=_diffusion)
    phase_frequencies: Mapping[str, float] = field(default_factory=_frequencies)
    initial_sigma: float = 0.25
    base_halflife: float = 50.0
    importance_maturity: int = 5
    importance_bonus_max: float = 0.5
    prune_threshold: float = 0.01
    max_packets: int = 500
    blend_amplitude_threshold: float = 0.1
    proximity_threshold: float = 0.3
    awareness_threshold: float = 0.6
    dominant_affect_threshold: float = 0.1
    deposit_amplitude_floor: float = 0.1
    min_deposit_intensity: float = 0.05
    helix_legacy_floor_before_gate: bool = True
    resonance_intensity_threshold: float = 0.5
    boredom_diversity_threshold: float = 0.4
    high_intensity_threshold: float = 0.8

    def __post_init__(self) -> None:
        if len(self.primaries) != 8 or tuple(self.primaries) != PRIMARIES:
            raise ValueError(
                "The standalone v1 state schema requires the canonical 8 Plutchik primaries"
            )
        for name in self.primaries:
            if name not in self.neutral_baselines:
                raise ValueError(f"Missing neutral baseline for {name}")
            if name not in self.diffusion_rates:
                raise ValueError(f"Missing diffusion rate for {name}")
            if name not in self.phase_frequencies:
                raise ValueError(f"Missing phase frequency for {name}")
        positive = {
            "initial_sigma": self.initial_sigma,
            "base_halflife": self.base_halflife,
            "importance_maturity": self.importance_maturity,
            "max_packets": self.max_packets,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")

    @property
    def dimensions(self) -> int:
        return len(self.primaries)

    @property
    def composite_frequency(self) -> float:
        return sum(self.phase_frequencies.values()) / len(self.phase_frequencies)

    @classmethod
    def corrected_gate(cls, **overrides: object) -> AffectConfig:
        """Use Helix dynamics with the negligible-event gate repaired."""
        return cls(helix_legacy_floor_before_gate=False, **overrides)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["primaries"] = list(self.primaries)
        return data
