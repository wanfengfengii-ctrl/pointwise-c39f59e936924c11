from dataclasses import dataclass
from fractions import Fraction

from analysis.closed_loop import build_closed_loop, initial_loop_state, step_closed_loop
from analysis.observation import resolve_observation, select_observation
from station.codec import load_evidence
from station.envelope import PublicPort, StationEvidence
from wiring.registry import WiringRevision


@dataclass(frozen=True, slots=True)
class ReplaySample:
    tick: int
    value: Fraction


def preview(
    first: StationEvidence | str,
    second: StationEvidence | str,
    wiring: WiringRevision,
    observation: PublicPort,
    ticks: int,
) -> tuple[ReplaySample, ...]:
    if type(ticks) is not int or ticks < 0:
        raise ValueError('preview ticks must be a nonnegative integer')
    loop = build_closed_loop(load_evidence(first), load_evidence(second), wiring)
    selected = resolve_observation(loop, observation)
    state = initial_loop_state(loop)
    samples = []
    for tick in range(ticks):
        state, outputs = step_closed_loop(loop, state)
        samples.append(ReplaySample(tick, select_observation(selected, outputs)))
    return tuple(samples)
