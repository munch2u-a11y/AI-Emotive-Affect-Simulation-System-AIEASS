"""Standalone Plutchik affect wave-packet system.

The core has no runtime dependencies and makes no model or network calls.
"""

from .config import AffectConfig
from .events import EVENT_TARGETS, event_vector
from .field import PlutchikWaveSystem
from .models import AffectResult, WavePacket
from .runtime import AffectRuntime

__version__ = "0.1.0"

# Compatibility aliases for the misspelling used in some discussions.
PutchnikWaveSystem = PlutchikWaveSystem
PutchnikAffectSystem = PlutchikWaveSystem

__all__ = [
    "EVENT_TARGETS",
    "AffectConfig",
    "AffectResult",
    "AffectRuntime",
    "PlutchikWaveSystem",
    "PutchnikAffectSystem",
    "PutchnikWaveSystem",
    "WavePacket",
    "__version__",
    "event_vector",
]
