"""Agent-framework-neutral session and message protocol."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Mapping
from pathlib import Path

from .config import AffectConfig
from .field import PlutchikWaveSystem


class AffectRuntime:
    """Multiplex independent affect fields by session ID.

    This is the boundary used by both the JSONL sidecar and MCP server. A
    framework can also call :meth:`process` directly from lifecycle hooks.
    """

    protocol_version = "plutchik-wave-jsonl-v1"

    def __init__(
        self,
        *,
        state_dir: str | Path | None = None,
        config: AffectConfig | None = None,
        autosave: bool = True,
    ) -> None:
        self.state_dir = Path(state_dir).resolve() if state_dir is not None else None
        self.config = config or AffectConfig()
        self.autosave = autosave
        self._systems: dict[str, PlutchikWaveSystem] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _session_key(session_id: object) -> str:
        value = str(session_id or "default").strip()
        if not value:
            value = "default"
        if len(value) > 256:
            raise ValueError("session_id is too long")
        return value

    def _state_path(self, session_id: str) -> Path | None:
        if self.state_dir is None:
            return None
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:24]
        return self.state_dir / f"session-{digest}.json"

    def get_system(self, session_id: object = "default") -> PlutchikWaveSystem:
        key = self._session_key(session_id)
        with self._lock:
            if key not in self._systems:
                state_path = self._state_path(key)
                self._systems[key] = PlutchikWaveSystem(
                    config=self.config,
                    state_path=state_path,
                    restore_state=bool(state_path and state_path.exists()),
                )
            return self._systems[key]

    def _save_if_configured(self, system: PlutchikWaveSystem) -> None:
        if self.autosave and system.state_path is not None:
            system.save_state()

    def process(self, message: Mapping[str, object]) -> dict[str, object]:
        """Process one framework-neutral protocol message.

        Every response is JSON serializable. Exceptions are intentionally not
        swallowed here; transports convert them to their native error format.
        """
        operation = str(message.get("op", "step"))
        session_id = self._session_key(message.get("session_id", "default"))
        system = self.get_system(session_id)

        if operation == "step":
            mode = str(message.get("mode", "lagrangian"))
            anchors = message.get("anchor_ids", [])
            if mode == "lagrangian":
                snapshot = message.get("snapshot", {})
                if not isinstance(snapshot, Mapping):
                    raise ValueError("snapshot must be an object")
                payload = system.step_lagrangian(
                    snapshot,
                    anchor_ids=anchors,  # type: ignore[arg-type]
                    stagnation_counter=int(message.get("stagnation_counter", 0)),
                )
            elif mode in {"affect", "direct"}:
                values = message.get("affect", {})
                if not isinstance(values, (Mapping, list, tuple)):
                    raise ValueError("affect must be an object or 8-value array")
                payload = system.step_affect(
                    values,
                    amplitude=message.get("amplitude"),  # type: ignore[arg-type]
                    anchor_ids=anchors,  # type: ignore[arg-type]
                )
            elif mode == "event":
                overrides = message.get("overrides")
                if overrides is not None and not isinstance(overrides, Mapping):
                    raise ValueError("overrides must be an object")
                payload = system.step_event(
                    str(message.get("event", "")),
                    magnitude=float(message.get("magnitude", 1.0)),
                    overrides=overrides,
                    anchor_ids=anchors,  # type: ignore[arg-type]
                )
            else:
                raise ValueError("mode must be 'lagrangian', 'affect', or 'event'")
            self._save_if_configured(system)
            return self._response(session_id, operation, payload)

        if operation == "sample":
            result = system.sample(
                message.get("affect_position"),  # type: ignore[arg-type]
                co_retrieved_memories=message.get("memory_ids", []),  # type: ignore[arg-type]
            )
            payload = {
                "result": result.to_dict(),
                "events": system.control_events(result),
                "context": system.render_context(result),
                "state": system.to_dict(),
            }
            return self._response(session_id, operation, payload)

        if operation == "evolve":
            system.evolve(
                accessed_memory_ids=message.get("memory_ids", []),  # type: ignore[arg-type]
                steps=int(message.get("steps", 1)),
            )
            self._save_if_configured(system)
            return self._response(session_id, operation, {"state": system.to_dict()})

        if operation == "state":
            return self._response(session_id, operation, {"state": system.to_dict()})

        if operation == "export":
            return self._response(
                session_id, operation, {"state": system.export_state()}
            )

        if operation == "context":
            result = system.sample()
            return self._response(
                session_id,
                operation,
                {"context": system.render_context(result), "result": result.to_dict()},
            )

        if operation == "save":
            path = system.save_state()
            return self._response(
                session_id, operation, {"saved": True, "path": str(path)}
            )

        if operation == "load":
            loaded = system.load_state()
            return self._response(
                session_id, operation, {"loaded": loaded, "state": system.to_dict()}
            )

        if operation == "reset":
            delete_saved = bool(message.get("delete_saved_state", False))
            system.reset(delete_saved_state=delete_saved)
            if not delete_saved:
                self._save_if_configured(system)
            return self._response(session_id, operation, {"state": system.to_dict()})

        raise ValueError(
            "op must be one of: step, sample, evolve, state, export, context, save, load, reset"
        )

    def _response(
        self,
        session_id: str,
        operation: str,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        return {
            "ok": True,
            "protocol_version": self.protocol_version,
            "session_id": session_id,
            "op": operation,
            **payload,
        }
