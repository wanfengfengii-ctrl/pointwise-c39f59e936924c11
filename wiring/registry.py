import hashlib
import json
import sqlite3
from dataclasses import dataclass

from station.envelope import PortGroup, station_ports, validate_port_group
from trial.model import validate_name
from trial.rationals import format_rational
from wiring.links import LINK_DELAY_TICKS, DirectedLink, build_directed_links
from wiring.ports import WiringPorts, resolve_wiring_ports


@dataclass(frozen=True, slots=True)
class WiringRevision:
    wiring_id: str
    ports: WiringPorts
    left_to_right: DirectedLink
    right_to_left: DirectedLink


def _port_fields(ports: PortGroup) -> tuple[str, str, str, str]:
    return (ports[0].station, *(port.name for port in ports))


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def _wiring_body(ports: WiringPorts, links: tuple[DirectedLink, DirectedLink]) -> str:
    return _canonical({
        'left': _port_fields(ports.left),
        'right': _port_fields(ports.right),
        'left_to_right': {'gain': format_rational(links[0].gain), 'delay': links[0].delay},
        'right_to_left': {'gain': format_rational(links[1].gain), 'delay': links[1].delay},
    })


def _fixed_id(body: str) -> str:
    return 'W-' + hashlib.sha256(body.encode('ascii')).hexdigest()


def _checked_body(wiring: WiringRevision) -> str:
    if not isinstance(wiring, WiringRevision) or not isinstance(wiring.ports, WiringPorts):
        raise ValueError('expected a fixed wiring revision')
    ports = resolve_wiring_ports(wiring.ports.left, wiring.ports.right)
    links = (wiring.left_to_right, wiring.right_to_left)
    for link in links:
        if not isinstance(link, DirectedLink) or type(link.delay) is not int:
            raise ValueError('invalid directed link')
    expected_links = build_directed_links(ports, links[0].gain, links[1].gain)
    if ports != wiring.ports or links != expected_links:
        raise ValueError('wiring links must match both directed one-tick connections')
    body = _wiring_body(ports, links)
    if _fixed_id(body) != wiring.wiring_id:
        raise ValueError('wiring id does not match the fixed contents')
    return body


def validate_wiring(wiring: WiringRevision) -> WiringRevision:
    _checked_body(wiring)
    return wiring


def _decode_port_fields(fields: list[str]) -> PortGroup:
    if not isinstance(fields, list) or len(fields) != 4:
        raise ValueError('invalid stored wiring port group')
    return station_ports(fields[0], fields[1:])


class WiringRegistry:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def initialize(self) -> None:
        with self._connection:
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS registered_wiring_ports (
                    port_group TEXT PRIMARY KEY
                )
            ''')
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS fixed_wiring (
                    wiring_id TEXT PRIMARY KEY,
                    body TEXT NOT NULL
                )
            ''')

    def register_ports(self, ports: PortGroup) -> PortGroup:
        ports = validate_port_group(ports)
        with self._connection:
            self._connection.execute('''
                INSERT INTO registered_wiring_ports (port_group) VALUES (?)
                ON CONFLICT (port_group) DO NOTHING
            ''', (_canonical(_port_fields(ports)),))
        return ports

    def get_ports(self, ports: PortGroup) -> PortGroup | None:
        ports = validate_port_group(ports)
        row = self._connection.execute('''
            SELECT port_group FROM registered_wiring_ports WHERE port_group = ?
        ''', (_canonical(_port_fields(ports)),)).fetchone()
        return None if row is None else _decode_port_fields(json.loads(row[0]))

    def publish(self, ports: WiringPorts, links: tuple[DirectedLink, DirectedLink]) -> WiringRevision:
        if self.get_ports(ports.left) is None or self.get_ports(ports.right) is None:
            raise KeyError('both complete port groups must be registered')
        body = _wiring_body(ports, links)
        wiring = WiringRevision(_fixed_id(body), ports, *links)
        validate_wiring(wiring)
        with self._connection:
            self._connection.execute('''
                INSERT INTO fixed_wiring (wiring_id, body) VALUES (?, ?)
                ON CONFLICT (wiring_id) DO NOTHING
            ''', (wiring.wiring_id, body))
            row = self._connection.execute('''
                SELECT body FROM fixed_wiring WHERE wiring_id = ?
            ''', (wiring.wiring_id,)).fetchone()
            if row is None or row[0] != body:
                raise ValueError('fixed wiring id already holds different contents')
        return wiring

    def get_fixed(self, wiring_id: str) -> WiringRevision | None:
        row = self._connection.execute('''
            SELECT body FROM fixed_wiring WHERE wiring_id = ?
        ''', (validate_name(wiring_id, 'wiring id'),)).fetchone()
        if row is None:
            return None
        record = json.loads(row[0])
        ports = resolve_wiring_ports(_decode_port_fields(record['left']), _decode_port_fields(record['right']))
        forward = record['left_to_right']
        backward = record['right_to_left']
        if any(type(link['delay']) is not int or link['delay'] != LINK_DELAY_TICKS for link in (forward, backward)):
            raise ValueError('invalid stored wiring delay')
        links = build_directed_links(ports, forward['gain'], backward['gain'])
        wiring = WiringRevision(wiring_id, ports, *links)
        if _checked_body(wiring) != row[0]:
            raise ValueError('fixed wiring contents do not match the stored record')
        return wiring
