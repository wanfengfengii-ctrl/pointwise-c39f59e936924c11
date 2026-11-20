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


def _observed_sequence(loop: ClosedLoop, observation: ObservationRef, count: int) -> list[Fraction]:
    state = initial_loop_state(loop)
    values: list[Fraction] = []
    for _ in range(count):
        state, outputs = step_closed_loop(loop, state)
        values.append(select_observation(observation, outputs))
    return values


def _berlekamp_massey(sequence: list[Fraction]) -> Polynomial:
    """Return the monic characteristic polynomial of the minimal linear recurrence."""
    connection = [Fraction(1)]
    previous = [Fraction(1)]
    order = 0
    shift = 1
    scale = Fraction(1)
    for index, value in enumerate(sequence):
        discrepancy = value
        for offset in range(1, order + 1):
            discrepancy += connection[offset] * sequence[index - offset]
        if discrepancy == 0:
            shift += 1
            continue
        coefficient = discrepancy / scale
        updated = list(connection)
        if len(updated) < len(previous) + shift:
            updated += [Fraction(0)] * (len(previous) + shift - len(updated))
        for offset, base in enumerate(previous):
            updated[offset + shift] -= coefficient * base
        if 2 * order <= index:
            order = index + 1 - order
            previous = list(connection)
            scale = discrepancy
            shift = 1
        else:
            shift += 1
        connection = updated
    connection = connection[:order + 1]
    while len(connection) < order + 1:
        connection.append(Fraction(0))
    return tuple(reversed(connection))


def _periodic_recurrence(loop: ClosedLoop, observation: ObservationRef) -> Polynomial:
    # Each residue class of the period obeys a fixed monodromy of the loop's
    # coordinate dimension, so the assembled minimal recurrence has order at
    # most ``period * dimension``. Sample well past twice that bound.
    dimension = len(initial_loop_state(loop).coordinates())
    count = 4 * dimension * loop.period + 2
    return _berlekamp_massey(_observed_sequence(loop, observation, count))


def _annihilator(loop: ClosedLoop, observation: ObservationRef) -> Polynomial:
    if loop.period == 1:
        return observed_recurrence(loop, observation)
    return _periodic_recurrence(loop, observation)


def decide_decay(loop: ClosedLoop, observation: ObservationRef) -> DecayVerdict:
    recurrence = _annihilator(loop, observation)
    if roots_strictly_inside_unit_disk(recurrence):
        return DecayVerdict.DECAY
    return DecayVerdict.NO_DECAY
