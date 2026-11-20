from dataclasses import dataclass
from fractions import Fraction

from analysis.closed_loop import ClosedLoop
from station.envelope import PublicPort


@dataclass(frozen=True, slots=True)
class ObservationRef:
    port: PublicPort
    index: int


def resolve_observation(loop: ClosedLoop, port: PublicPort) -> ObservationRef:
    if not isinstance(port, PublicPort) or port.purpose != 'observation':
        raise ValueError('specify a full observation port identity')
    for index, evidence in enumerate((loop.left, loop.right)):
        if evidence.ports[2] == port:
            return ObservationRef(evidence.ports[2], index)
    raise ValueError('observation port does not belong to the fixed pair')


def select_observation(observation: ObservationRef, outputs: tuple[Fraction, Fraction]) -> Fraction:
    return outputs[observation.index]
