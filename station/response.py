from dataclasses import dataclass
from fractions import Fraction

from trial.cutoff import CutoffState
from trial.model import Dynamics, StationModel, Vector, parse_vector, validate_dynamics


@dataclass(frozen=True, slots=True)
class StationResponse:
    dynamics: Dynamics
    initial_state: Vector


def build_response(model: StationModel, cutoff: CutoffState) -> StationResponse:
    dynamics = validate_dynamics(model.dynamics)
    initial = parse_vector(cutoff.initial_state, dynamics.dimension, 'cutoff state')
    return StationResponse(dynamics, initial)


def _dot(row: Vector, state: Vector) -> Fraction:
    return sum((coefficient * value for coefficient, value in zip(row, state, strict=True)), Fraction(0))


def public_output(response: StationResponse, state: Vector, incoming: Fraction) -> tuple[Fraction, Fraction]:
    dynamics = response.dynamics
    returned = _dot(dynamics.return_vector, state) + dynamics.return_feedthrough * incoming
    observed = _dot(dynamics.observation_vector, state) + dynamics.observation_feedthrough * incoming
    return returned, observed


def advance_state(response: StationResponse, state: Vector, incoming: Fraction) -> Vector:
    dynamics = response.dynamics
    return tuple(
        _dot(row, state) + coefficient * incoming
        for row, coefficient in zip(dynamics.transition, dynamics.input_vector, strict=True)
    )
