from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from trial.rationals import format_rational, parse_rational

Vector = tuple[Fraction, ...]
Matrix = tuple[Vector, ...]
MAX_STATES = 3
_DYNAMICS_FIELDS = {
    'transition', 'input_vector', 'return_vector', 'return_feedthrough',
    'observation_vector', 'observation_feedthrough',
}


@dataclass(frozen=True, slots=True)
class Dynamics:
    transition: Matrix
    input_vector: Vector
    return_vector: Vector
    return_feedthrough: Fraction
    observation_vector: Vector
    observation_feedthrough: Fraction

    @property
    def dimension(self) -> int:
        return len(self.transition)


@dataclass(frozen=True, slots=True)
class StationModel:
    ports: tuple[str, str, str]
    dynamics: Dynamics

    @property
    def dimension(self) -> int:
        return self.dynamics.dimension


@dataclass(frozen=True, slots=True)
class PeriodicModel:
    ports: tuple[str, str, str]
    stages: tuple[Dynamics, ...]
    phase: int

    @property
    def dimension(self) -> int:
        return self.stages[0].dimension


def validate_name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or not value.isprintable():
        raise ValueError(f'{label} must be nonempty printable text with no edge whitespace')
    return value


def parse_vector(values: object, size: int, label: str) -> Vector:
    if not isinstance(values, (tuple, list)) or len(values) != size:
        raise ValueError(f'{label} must have exactly {size} entries')
    try:
        return tuple(parse_rational(value) for value in values)
    except ValueError as exc:
        raise ValueError(f'{label} contains an invalid rational') from exc


def validate_dynamics(value: object) -> Dynamics:
    if isinstance(value, Dynamics):
        fields = {field: getattr(value, field) for field in _DYNAMICS_FIELDS}
    elif isinstance(value, Mapping) and value.keys() == _DYNAMICS_FIELDS:
        fields = value
    else:
        raise ValueError('model dynamics fields do not match the station model')
    transition = fields['transition']
    if not isinstance(transition, (tuple, list)) or len(transition) > MAX_STATES:
        raise ValueError('transition must contain zero to three rows')
    size = len(transition)
    return Dynamics(
        tuple(parse_vector(row, size, 'transition row') for row in transition),
        parse_vector(fields['input_vector'], size, 'input vector'),
        parse_vector(fields['return_vector'], size, 'return vector'),
        parse_rational(fields['return_feedthrough']),
        parse_vector(fields['observation_vector'], size, 'observation vector'),
        parse_rational(fields['observation_feedthrough']),
    )


def validate_model(value: object) -> StationModel:
    if isinstance(value, StationModel):
        names, dynamics = value.ports, value.dynamics
    elif isinstance(value, Mapping) and value.keys() == _DYNAMICS_FIELDS | {'ports'}:
        names = value['ports']
        dynamics = {key: value[key] for key in _DYNAMICS_FIELDS}
    else:
        raise ValueError('station model must specify its ports and dynamics')
    if not isinstance(names, (list, tuple)) or len(names) != 3:
        raise ValueError('model must specify input, return and observation port names')
    ports = tuple(validate_name(name, 'port name') for name in names)
    return StationModel(ports, validate_dynamics(dynamics))


MAX_STAGES = 3
_PERIODIC_FIELDS = {'ports', 'stages', 'phase'}


def validate_periodic_model(value: object) -> PeriodicModel:
    if isinstance(value, PeriodicModel):
        names, stages, phase = value.ports, value.stages, value.phase
    elif isinstance(value, Mapping) and value.keys() == _PERIODIC_FIELDS:
        names, stages, phase = value['ports'], value['stages'], value['phase']
    else:
        raise ValueError('periodic model must specify ports, stages and phase')
    if not isinstance(names, (list, tuple)) or len(names) != 3:
        raise ValueError('model must specify input, return and observation port names')
    ports = tuple(validate_name(name, 'port name') for name in names)
    if not isinstance(stages, (list, tuple)) or not 1 <= len(stages) <= MAX_STAGES:
        raise ValueError('stages must contain one to three ordered stages')
    parsed_stages = tuple(validate_dynamics(stage) for stage in stages)
    dimension = parsed_stages[0].dimension
    if any(stage.dimension != dimension for stage in parsed_stages):
        raise ValueError('every stage must use the same state coordinates')
    if type(phase) is not int or not 0 <= phase < len(parsed_stages):
        raise ValueError('phase must be a non-boolean stage index within range')
    return PeriodicModel(ports, parsed_stages, phase)


def validate_station_or_periodic(value: object) -> StationModel | PeriodicModel:
    if isinstance(value, PeriodicModel):
        return validate_periodic_model(value)
    if isinstance(value, Mapping) and value.keys() == _PERIODIC_FIELDS:
        return validate_periodic_model(value)
    return validate_model(value)


def dynamics_payload(dynamics: Dynamics) -> dict:
    def coefficients(row: Vector) -> list[str]:
        return [format_rational(value) for value in row]

    return {
        'transition': [coefficients(row) for row in dynamics.transition],
        'input_vector': coefficients(dynamics.input_vector),
        'return_vector': coefficients(dynamics.return_vector),
        'return_feedthrough': format_rational(dynamics.return_feedthrough),
        'observation_vector': coefficients(dynamics.observation_vector),
        'observation_feedthrough': format_rational(dynamics.observation_feedthrough),
    }


def stages_payload(stages: tuple[Dynamics, ...]) -> list[dict]:
    return [dynamics_payload(stage) for stage in stages]
