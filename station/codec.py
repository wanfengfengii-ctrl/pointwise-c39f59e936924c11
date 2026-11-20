import hashlib
import json
from dataclasses import asdict

from station.envelope import PortGroup, PublicPort, StationEvidence, validate_envelope
from station.response import StationResponse
from trial.model import dynamics_payload, parse_vector, validate_dynamics
from trial.rationals import format_rational

_VERSION = 1
_ENVELOPE_FIELDS = {'version', 'evidence_id', 'trial', 'station', 'revision', 'ports', 'response'}


def _canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def _body(trial: str, station: str, revision: int, ports: PortGroup, response: StationResponse) -> dict:
    return {
        'version': _VERSION,
        'trial': trial,
        'station': station,
        'revision': revision,
        'ports': [asdict(port) for port in ports],
        'response': {
            'dynamics': dynamics_payload(response.dynamics),
            'initial_state': [format_rational(value) for value in response.initial_state],
        },
    }


def _fixed_id(body: dict) -> str:
    return 'E-' + hashlib.sha256(_canonical_json(body).encode('ascii')).hexdigest()


def seal_evidence(
    trial: str, station: str, revision: int, ports: PortGroup, response: StationResponse
) -> StationEvidence:
    body = _body(trial, station, revision, ports, response)
    evidence = StationEvidence(_fixed_id(body), trial, station, revision, ports, response)
    return validate_envelope(evidence)


def _checked_body(evidence: StationEvidence) -> dict:
    validate_envelope(evidence)
    body = _body(evidence.trial, evidence.station, evidence.revision, evidence.ports, evidence.response)
    if evidence.evidence_id != _fixed_id(body):
        raise ValueError('evidence id does not match the fixed contents')
    return body


def encode_evidence(evidence: StationEvidence) -> str:
    return _canonical_json({'evidence_id': evidence.evidence_id, **_checked_body(evidence)})


def _unique_json_object(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'duplicate station evidence field: {key}')
        result[key] = value
    return result


def decode_evidence(text: str) -> StationEvidence:
    if not isinstance(text, str):
        raise ValueError('station evidence must be JSON text')
    try:
        document = json.loads(text, object_pairs_hook=_unique_json_object)
    except json.JSONDecodeError as exc:
        raise ValueError('malformed station evidence JSON') from exc
    if not isinstance(document, dict) or document.keys() != _ENVELOPE_FIELDS:
        raise ValueError('invalid station evidence fields')
    if type(document['version']) is not int or document['version'] != _VERSION:
        raise ValueError('unsupported station evidence version')
    raw_ports = document['ports']
    if not isinstance(raw_ports, list) or len(raw_ports) != 3:
        raise ValueError('invalid station evidence port list')
    ports = []
    for raw_port in raw_ports:
        if not isinstance(raw_port, dict) or raw_port.keys() != {'station', 'purpose', 'name'}:
            raise ValueError('invalid public port fields')
        ports.append(PublicPort(**raw_port))
    raw_response = document['response']
    if not isinstance(raw_response, dict) or raw_response.keys() != {'dynamics', 'initial_state'}:
        raise ValueError('invalid station response fields')
    dynamics = validate_dynamics(raw_response['dynamics'])
    initial = parse_vector(raw_response['initial_state'], dynamics.dimension, 'response initial state')
    evidence = StationEvidence(
        document['evidence_id'], document['trial'], document['station'], document['revision'],
        tuple(ports), StationResponse(dynamics, initial),
    )
    _checked_body(evidence)
    return evidence


def load_evidence(value: StationEvidence | str) -> StationEvidence:
    if isinstance(value, str):
        return decode_evidence(value)
    _checked_body(value)
    return value
