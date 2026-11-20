from dataclasses import dataclass

from station.envelope import PortGroup, StationEvidence, validate_port_group


@dataclass(frozen=True, slots=True)
class WiringPorts:
    left: PortGroup
    right: PortGroup


def resolve_wiring_ports(left: PortGroup, right: PortGroup) -> WiringPorts:
    left = validate_port_group(left)
    right = validate_port_group(right)
    if left[0].station == right[0].station:
        raise ValueError('wiring must connect distinct stations')
    return WiringPorts(left, right)


def match_station_ports(
    ports: WiringPorts, first: StationEvidence, second: StationEvidence
) -> tuple[StationEvidence, StationEvidence]:
    if first.ports == ports.left and second.ports == ports.right:
        return first, second
    if second.ports == ports.left and first.ports == ports.right:
        return second, first
    raise ValueError('station evidence does not match the fixed wiring ports')
