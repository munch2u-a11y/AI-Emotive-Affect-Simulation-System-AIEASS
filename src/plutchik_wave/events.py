"""Portable, deterministic operational-event adapter.

These templates are integration heuristics, not part of Plutchik theory and
not a psychological classifier. Hosts can bypass them with direct vectors.
"""

from __future__ import annotations

from collections.abc import Mapping

from .config import AffectConfig
from .models import clamp, finite_float

EVENT_TARGETS: dict[str, dict[str, float]] = {
    "tool_success": {"joy": 0.85, "trust": 0.75, "anticipation": 0.65},
    "tool_failure": {
        "sadness": 0.45,
        "surprise": 0.50,
        "anger": 0.25,
        "anticipation": 0.30,
    },
    "goal_progress": {"joy": 0.70, "trust": 0.65, "anticipation": 0.90},
    "blocked": {"sadness": 0.30, "disgust": 0.35, "anger": 0.65, "anticipation": 0.35},
    "novelty": {"surprise": 0.90, "anticipation": 0.80, "fear": 0.15},
    "risk_detected": {
        "fear": 0.80,
        "surprise": 0.40,
        "anticipation": 0.80,
        "trust": 0.30,
    },
    "user_trust": {"joy": 0.70, "trust": 0.95, "anticipation": 0.60},
    "user_rejection": {
        "joy": 0.20,
        "trust": 0.20,
        "sadness": 0.70,
        "disgust": 0.40,
        "anger": 0.35,
        "anticipation": 0.25,
    },
    "uncertainty": {
        "trust": 0.35,
        "fear": 0.45,
        "surprise": 0.55,
        "anticipation": 0.70,
    },
    "stagnation": {"joy": 0.25, "sadness": 0.25, "disgust": 0.35, "anticipation": 0.15},
    "recovery": {
        "joy": 0.75,
        "trust": 0.70,
        "fear": 0.10,
        "sadness": 0.10,
        "anticipation": 0.80,
    },
}

EVENT_ALIASES = {
    "success": "tool_success",
    "failure": "tool_failure",
    "progress": "goal_progress",
    "risk": "risk_detected",
    "trust": "user_trust",
    "rejection": "user_rejection",
}


def event_vector(
    event: str,
    *,
    magnitude: float = 1.0,
    config: AffectConfig,
    overrides: Mapping[str, object] | None = None,
) -> dict[str, float]:
    """Interpolate from neutral state to an operational event target."""
    canonical = EVENT_ALIASES.get(event.strip().lower(), event.strip().lower())
    if canonical not in EVENT_TARGETS:
        available = ", ".join(sorted(EVENT_TARGETS))
        raise ValueError(f"Unknown event '{event}'. Available events: {available}")
    strength = clamp(finite_float(magnitude, "magnitude"))
    target = dict(config.neutral_baselines)
    target.update(EVENT_TARGETS[canonical])
    if overrides:
        unknown = set(overrides) - set(config.primaries)
        if unknown:
            raise ValueError(f"Unknown affect dimensions: {', '.join(sorted(unknown))}")
        target.update(
            {
                name: clamp(finite_float(value, name))
                for name, value in overrides.items()
            }
        )
    return {
        name: config.neutral_baselines[name]
        + (target[name] - config.neutral_baselines[name]) * strength
        for name in config.primaries
    }
