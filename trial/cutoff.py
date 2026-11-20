from dataclasses import dataclass

from trial.model import StationModel, Vector, parse_vector


@dataclass(frozen=True, slots=True)
class CutoffState:
    initial_state: Vector
    source: str


def validate_cutoff(model: StationModel, initial_state: object, source: object) -> CutoffState:
    state = parse_vector(initial_state, model.dynamics.dimension, 'cutoff state')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('original measurement source is required')
    return CutoffState(state, source)
