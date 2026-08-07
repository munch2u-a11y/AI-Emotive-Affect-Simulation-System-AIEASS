"""Minimal host-lifecycle integration using operational events."""

from dataclasses import dataclass

from plutchik_wave import PlutchikWaveSystem


@dataclass
class Cycle:
    cycle_id: str
    tool_failed: bool = False
    made_progress: bool = False
    novel_information: bool = False


def update_affect(cycle: Cycle, system: PlutchikWaveSystem) -> dict[str, object]:
    if cycle.tool_failed:
        event = "tool_failure"
    elif cycle.made_progress:
        event = "goal_progress"
    elif cycle.novel_information:
        event = "novelty"
    else:
        event = "uncertainty"
    return system.step_event(event, anchor_ids=[cycle.cycle_id])


if __name__ == "__main__":
    field = PlutchikWaveSystem(state_path="agent-affect.json")
    update = update_affect(
        Cycle("cycle-1", made_progress=True, novel_information=True), field
    )
    print(update["context"])
    print(update["result"]["steering_vector"])
    field.save_state()
