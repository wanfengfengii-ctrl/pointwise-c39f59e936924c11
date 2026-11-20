from dataclasses import dataclass

from station.response import StationResponse
from trial.model import parse_vector, validate_dynamics, validate_name
from trial.revisions import revision_key

PORT_PURPOSES = ('input', 'return', 'observation')


@dataclass(frozen=True, slots=True)
class PublicPort:
    station: str
    purpose: str
    name: str


PortGroup = tuple[PublicPort, PublicPort, PublicPort]


def station_ports(station: str, names: tuple[str, str, str]) -> PortGroup:
    validate_name(station, 'station')
    if not isinstance(names, (tuple, list)) or len(names) != len(PORT_PURPOSES):
        raise ValueError('a station requires three named public ports')
    return tuple(
        PublicPort(station, purpose, validate_name(name, 'port name'))
        for purpose, name in zip(PORT_PURPOSES, names, strict=True)
    )


def validate_port_group(group: object) -> PortGroup:
    if not isinstance(group, (tuple, list)) or len(group) != len(PORT_PURPOSES):
        raise ValueError('a port group must contain input, return and observation ports')
    if any(not isinstance(port, PublicPort) for port in group):
        raise ValueError('expected full public port identities')
    ports = tuple(group)
    expected = station_ports(ports[0].station, tuple(port.name for port in ports))
    if ports != expected:
        raise ValueError('port group has inconsistent station or purpose')
    return expected


@dataclass(frozen=True, slots=True)
class StationEvidence:
    evidence_id: str
    trial: str
    station: str
    revision: int
    ports: PortGroup
    response: StationResponse


def validate_envelope(evidence: StationEvidence) -> StationEvidence:
    if not isinstance(evidence, StationEvidence):
        raise ValueError('expected a station evidence envelope')
    validate_name(evidence.evidence_id, 'evidence id')
    revision_key(evidence.trial, evidence.station, evidence.revision)
    ports = validate_port_group(evidence.ports)
    if evidence.ports != ports or ports[0].station != evidence.station:
        raise ValueError('evidence ports do not match the source station')
    if not isinstance(evidence.response, StationResponse):
        raise ValueError('expected a public station response')
    response = evidence.response
    dynamics = validate_dynamics(response.dynamics)
    initial = parse_vector(response.initial_state, dynamics.dimension, 'response initial state')
    if response != StationResponse(dynamics, initial):
        raise ValueError('station response must be in normalized coordinates')
    return evidence
