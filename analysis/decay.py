from enum import Enum
from fractions import Fraction

from analysis.closed_loop import ClosedLoop, initial_loop_state, step_closed_loop
from analysis.observation import ObservationRef, select_observation
from analysis.polynomial import Polynomial, poly_add, poly_divmod, poly_gcd, poly_multiply, poly_trim
from analysis.unit_disk import roots_strictly_inside_unit_disk
from trial.model import Vector


class DecayVerdict(str, Enum):
    DECAY = 'decay'
    NO_DECAY = 'no_decay'


def _state_relation(loop: ClosedLoop, observation: ObservationRef) -> tuple[Polynomial, Vector]:
    """Find a relation on the actual state orbit and collect the corresponding output prefix."""
    state = initial_loop_state(loop)
    dimension = len(state.coordinates())
    basis: list[tuple[int, Vector, Polynomial]] = []
    prefix = []
    for degree in range(dimension + 1):
        coordinates = state.coordinates()
        relation = (Fraction(0),) * degree + (Fraction(1),)
        for pivot, direction, weights in basis:
            scale = coordinates[pivot]
            if scale:
                coordinates = tuple(a - scale * b for a, b in zip(coordinates, direction, strict=True))
                relation = poly_add(relation, tuple(-scale * coefficient for coefficient in weights))
        pivot = next((index for index, value in enumerate(coordinates) if value), None)
        if pivot is None:
            # Linearity propagates this relation to every later tick of the orbit.
            return relation, tuple(prefix)
        scale = coordinates[pivot]
        basis.append((
            pivot,
            tuple(value / scale for value in coordinates),
            tuple(coefficient / scale for coefficient in relation),
        ))
        state, outputs = step_closed_loop(loop, state)
        prefix.append(select_observation(observation, outputs))
    raise ArithmeticError('state orbit exceeded its coordinate dimension')


def observed_recurrence(loop: ClosedLoop, observation: ObservationRef) -> Polynomial:
    """Return the monic forward-shift annihilator of the actual selected sequence."""
    state_relation, prefix = _state_relation(loop, observation)
    # In the power series of the observations, reversing the state relation
    # makes every coefficient from len(prefix) onward vanish after multiplication.
    denominator = poly_trim(reversed(state_relation))
    numerator = poly_trim(poly_multiply(denominator, prefix)[:len(prefix)])
    if not numerator:
        return (Fraction(1),)
    common = poly_gcd(numerator, denominator)
    numerator, _ = poly_divmod(numerator, common)
    denominator, _ = poly_divmod(denominator, common)
    normalized = tuple(coefficient / denominator[0] for coefficient in denominator)
    # A polynomial part is a finite transient and contributes zero forward roots.
    order = max(len(normalized) - 1, len(numerator))
    return tuple(reversed(normalized + (Fraction(0),) * (order + 1 - len(normalized))))


def decide_decay(loop: ClosedLoop, observation: ObservationRef) -> DecayVerdict:
    recurrence = observed_recurrence(loop, observation)
    if roots_strictly_inside_unit_disk(recurrence):
        return DecayVerdict.DECAY
    return DecayVerdict.NO_DECAY
