from dataclasses import dataclass
from fractions import Fraction

from station.envelope import StationEvidence, validate_envelope
from station.response import advance_state, public_output
from trial.model import Vector
from wiring.ports import match_station_ports
from wiring.registry import WiringRevision, validate_wiring


@dataclass(frozen=True, slots=True)
class ClosedLoop:
    left: StationEvidence
    right: StationEvidence
    wiring: WiringRevision


@dataclass(frozen=True, slots=True)
class LoopState:
    left_state: Vector
    right_state: Vector
    left_incoming: Fraction
    right_incoming: Fraction

    def coordinates(self) -> Vector:
        return (*self.left_state, *self.right_state, self.left_incoming, self.right_incoming)


def build_closed_loop(first: StationEvidence, second: StationEvidence, wiring: WiringRevision) -> ClosedLoop:
    validate_wiring(wiring)
    left, right = match_station_ports(wiring.ports, validate_envelope(first), validate_envelope(second))
    return ClosedLoop(left, right, wiring)


def initial_loop_state(loop: ClosedLoop) -> LoopState:
    return LoopState(loop.left.response.initial_state, loop.right.response.initial_state, Fraction(0), Fraction(0))


def step_closed_loop(loop: ClosedLoop, state: LoopState) -> tuple[LoopState, tuple[Fraction, Fraction]]:
    left_response = loop.left.response
    right_response = loop.right.response
    left_return, left_observed = public_output(left_response, state.left_state, state.left_incoming)
    right_return, right_observed = public_output(right_response, state.right_state, state.right_incoming)
    next_state = LoopState(
        advance_state(left_response, state.left_state, state.left_incoming),
        advance_state(right_response, state.right_state, state.right_incoming),
        loop.wiring.right_to_left.gain * right_return,
        loop.wiring.left_to_right.gain * left_return,
    )
    return next_state, (left_observed, right_observed)
