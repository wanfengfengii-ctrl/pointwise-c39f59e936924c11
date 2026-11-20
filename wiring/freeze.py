from station.envelope import PortGroup
from wiring.links import build_directed_links
from wiring.ports import resolve_wiring_ports
from wiring.registry import WiringRegistry, WiringRevision


def freeze_wiring(
    registry: WiringRegistry,
    left_ports: PortGroup,
    right_ports: PortGroup,
    left_to_right: object,
    right_to_left: object,
) -> WiringRevision:
    requested = resolve_wiring_ports(left_ports, right_ports)
    left = registry.get_ports(requested.left)
    right = registry.get_ports(requested.right)
    if left is None or right is None:
        raise KeyError('both complete port groups must be registered')
    ports = resolve_wiring_ports(left, right)
    links = build_directed_links(ports, left_to_right, right_to_left)
    return registry.publish(ports, links)
