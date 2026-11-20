from dataclasses import dataclass
from fractions import Fraction

from station.envelope import PublicPort
from trial.rationals import parse_rational
from wiring.ports import WiringPorts

LINK_DELAY_TICKS = 1


@dataclass(frozen=True, slots=True)
class DirectedLink:
    source: PublicPort
    destination: PublicPort
    gain: Fraction
    delay: int = LINK_DELAY_TICKS


def build_directed_links(
    ports: WiringPorts, left_to_right: object, right_to_left: object
) -> tuple[DirectedLink, DirectedLink]:
    left_gain = parse_rational(left_to_right)
    right_gain = parse_rational(right_to_left)
    return (
        DirectedLink(ports.left[1], ports.right[0], left_gain),
        DirectedLink(ports.right[1], ports.left[0], right_gain),
    )
