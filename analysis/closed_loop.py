from dataclasses import dataclass
from fractions import Fraction
from math import gcd

from station.envelope import StationEvidence, validate_envelope
from station.response import (
    PeriodicResponse,
    PublicResponse,
    stage_advance,
    stage_at,
    stage_count,
    stage_output,
)
from trial.model import Vector
from wiring.ports import match_station_ports
from wiring.registry import WiringRevision, validate_wiring


@dataclass(frozen=True, slots=True)
class ClosedLoop:
    left: StationEvidence
    right: StationEvidence
    wiring: WiringRevision
    period: int


@dataclass(frozen=True, slots=True)
class LoopState:
    left_state: Vector
    right_state: Vector
    left_incoming: Fraction
    right_incoming: Fraction
    tick: int = 0

    def coordinates(self) -> Vector:
        return (*self.left_state, *self.right_state, self.left_incoming, self.right_incoming)


def response_version(response: PublicResponse) -> int:
    return 2 if isinstance(response, PeriodicResponse) else 1


def loop_period(left: PublicResponse, right: PublicResponse) -> int:
    a, b = stage_count(left), stage_count(right)
    return a // gcd(a, b) * b


def build_closed_loop(first: StationEvidence, second: StationEvidence, wiring: WiringRevision) -> ClosedLoop:
    validate_wiring(wiring)
    left_evidence = validate_envelope(first)
    right_evidence = validate_envelope(second)
    if response_version(left_evidence.response) != response_version(right_evidence.response):
        raise ValueError('both station evidences must use the same evidence version')
    if response_version(left_evidence.response) == 2 and left_evidence.trial != right_evidence.trial:
        raise ValueError('periodic station evidences must come from the same trial')
    left, right = match_station_ports(wiring.ports, left_evidence, right_evidence)
    return ClosedLoop(left, right, wiring, loop_period(left.response, right.response))


def initial_loop_state(loop: ClosedLoop) -> LoopState:
    return LoopState(
        loop.left.response.initial_state,
        loop.right.response.initial_state,
        Fraction(0),
        Fraction(0),
        0,
    )


def step_closed_loop(loop: ClosedLoop, state: LoopState) -> tuple[LoopState, tuple[Fraction, Fraction]]:
    left_stage = stage_at(loop.left.response, state.tick)
    right_stage = stage_at(loop.right.response, state.tick)
    left_return, left_observed = stage_output(left_stage, state.left_state, state.left_incoming)
    right_return, right_observed = stage_output(right_stage, state.right_state, state.right_incoming)
    next_state = LoopState(
        stage_advance(left_stage, state.left_state, state.left_incoming),
        stage_advance(right_stage, state.right_state, state.right_incoming),
        loop.wiring.right_to_left.gain * right_return,
        loop.wiring.left_to_right.gain * left_return,
        state.tick + 1,
    )
    return next_state, (left_observed, right_observed)
