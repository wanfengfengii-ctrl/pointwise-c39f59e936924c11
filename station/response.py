from dataclasses import dataclass
from fractions import Fraction

from trial.cutoff import CutoffState
from trial.model import (
    Dynamics,
    PeriodicModel,
    StationModel,
    Vector,
    parse_vector,
    validate_dynamics,
)


@dataclass(frozen=True, slots=True)
class StationResponse:
    dynamics: Dynamics
    initial_state: Vector


@dataclass(frozen=True, slots=True)
class PeriodicResponse:
    stages: tuple[Dynamics, ...]
    initial_state: Vector
    phase: int

    @property
    def dimension(self) -> int:
        return self.stages[0].dimension


PublicResponse = StationResponse | PeriodicResponse


def build_response(model: StationModel, cutoff: CutoffState) -> StationResponse:
    dynamics = validate_dynamics(model.dynamics)
    initial = parse_vector(cutoff.initial_state, dynamics.dimension, 'cutoff state')
    return StationResponse(dynamics, initial)


def build_periodic_response(model: PeriodicModel, cutoff: CutoffState) -> PeriodicResponse:
    stages = tuple(validate_dynamics(stage) for stage in model.stages)
    if not stages or any(stage.dimension != stages[0].dimension for stage in stages):
        raise ValueError('every stage must use the same state coordinates')
    if type(model.phase) is not int or not 0 <= model.phase < len(stages):
        raise ValueError('phase must be a non-boolean stage index within range')
    initial = parse_vector(cutoff.initial_state, stages[0].dimension, 'cutoff state')
    return PeriodicResponse(stages, initial, model.phase)


def stage_count(response: PublicResponse) -> int:
    if isinstance(response, PeriodicResponse):
        return len(response.stages)
    return 1


def stage_at(response: PublicResponse, tick: int) -> Dynamics:
    if isinstance(response, PeriodicResponse):
        return response.stages[(response.phase + tick) % len(response.stages)]
    return response.dynamics


def _dot(row: Vector, state: Vector) -> Fraction:
    return sum((coefficient * value for coefficient, value in zip(row, state, strict=True)), Fraction(0))


def stage_output(dynamics: Dynamics, state: Vector, incoming: Fraction) -> tuple[Fraction, Fraction]:
    returned = _dot(dynamics.return_vector, state) + dynamics.return_feedthrough * incoming
    observed = _dot(dynamics.observation_vector, state) + dynamics.observation_feedthrough * incoming
    return returned, observed


def stage_advance(dynamics: Dynamics, state: Vector, incoming: Fraction) -> Vector:
    return tuple(
        _dot(row, state) + coefficient * incoming
        for row, coefficient in zip(dynamics.transition, dynamics.input_vector, strict=True)
    )


def public_output(
    response: StationResponse, state: Vector, incoming: Fraction
) -> tuple[Fraction, Fraction]:
    return stage_output(response.dynamics, state, incoming)


def advance_state(response: StationResponse, state: Vector, incoming: Fraction) -> Vector:
    return stage_advance(response.dynamics, state, incoming)
