import hashlib
import json
from dataclasses import asdict

from station.envelope import PortGroup, PublicPort, StationEvidence, validate_envelope
from station.response import PeriodicResponse, StationResponse
from trial.model import (
    dynamics_payload,
    parse_vector,
    stages_payload,
    validate_dynamics,
)
from trial.rationals import format_rational

_ENVELOPE_FIELDS = {'version', 'evidence_id', 'trial', 'station', 'revision', 'ports', 'response'}
_V1_RESPONSE_FIELDS = {'dynamics', 'initial_state'}
_V2_RESPONSE_FIELDS = {'initial_state', 'stages', 'phase'}


def _canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def evidence_version(response: StationResponse | PeriodicResponse) -> int:
    return 2 if isinstance(response, PeriodicResponse) else 1


def _body(
    trial: str,
    station: str,
    revision: int,
    ports: PortGroup,
    response: StationResponse | PeriodicResponse,
) -> dict:
    common = {
        'trial': trial,
        'station': station,
        'revision': revision,
        'ports': [asdict(port) for port in ports],
    }
    if isinstance(response, PeriodicResponse):
        return {
            'version': 2,
            **common,
            'response': {
                'initial_state': [format_rational(value) for value in response.initial_state],
                'stages': stages_payload(response.stages),
                'phase': response.phase,
            },
        }
    return {
        'version': 1,
        **common,
        'response': {
            'dynamics': dynamics_payload(response.dynamics),
            'initial_state': [format_rational(value) for value in response.initial_state],
        },
    }


def _fixed_id(body: dict) -> str:
    return 'E-' + hashlib.sha256(_canonical_json(body).encode('ascii')).hexdigest()


def seal_evidence(
    trial: str,
    station: str,
    revision: int,
    ports: PortGroup,
    response: StationResponse | PeriodicResponse,
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


def _decode_ports(raw_ports: object) -> tuple[PublicPort, ...]:
    if not isinstance(raw_ports, list) or len(raw_ports) != 3:
        raise ValueError('invalid station evidence port list')
    ports = []
    for raw_port in raw_ports:
        if not isinstance(raw_port, dict) or raw_port.keys() != {'station', 'purpose', 'name'}:
            raise ValueError('invalid public port fields')
        ports.append(PublicPort(**raw_port))
    return tuple(ports)


def _decode_v1_response(raw_response: object) -> StationResponse:
    if not isinstance(raw_response, dict) or raw_response.keys() != _V1_RESPONSE_FIELDS:
        raise ValueError('invalid station response fields')
    dynamics = validate_dynamics(raw_response['dynamics'])
    initial = parse_vector(raw_response['initial_state'], dynamics.dimension, 'response initial state')
    return StationResponse(dynamics, initial)


def _decode_v2_response(raw_response: object) -> PeriodicResponse:
    if not isinstance(raw_response, dict) or raw_response.keys() != _V2_RESPONSE_FIELDS:
        raise ValueError('invalid periodic station response fields')
    raw_stages = raw_response['stages']
    if not isinstance(raw_stages, list) or not 1 <= len(raw_stages) <= 3:
        raise ValueError('periodic response requires one to three stages')
    stages = tuple(validate_dynamics(stage) for stage in raw_stages)
    dimension = stages[0].dimension
    if any(stage.dimension != dimension for stage in stages):
        raise ValueError('every stage must use the same state coordinates')
    initial = parse_vector(raw_response['initial_state'], dimension, 'response initial state')
    phase = raw_response['phase']
    if type(phase) is not int or not 0 <= phase < len(stages):
        raise ValueError('phase must be a non-boolean stage index within range')
    return PeriodicResponse(stages, initial, phase)


def decode_evidence(text: str) -> StationEvidence:
    if not isinstance(text, str):
        raise ValueError('station evidence must be JSON text')
    try:
        document = json.loads(text, object_pairs_hook=_unique_json_object)
    except json.JSONDecodeError as exc:
        raise ValueError('malformed station evidence JSON') from exc
    if not isinstance(document, dict) or document.keys() != _ENVELOPE_FIELDS:
        raise ValueError('invalid station evidence fields')
    version = document['version']
    if type(version) is not int or version not in (1, 2):
        raise ValueError('unsupported station evidence version')
    ports = _decode_ports(document['ports'])
    raw_response = document['response']
    expected_fields = _V2_RESPONSE_FIELDS if version == 2 else _V1_RESPONSE_FIELDS
    if not isinstance(raw_response, dict) or raw_response.keys() != expected_fields:
        raise ValueError('station response fields do not match the declared version')
    response = _decode_v2_response(raw_response) if version == 2 else _decode_v1_response(raw_response)
    evidence = StationEvidence(
        document['evidence_id'], document['trial'], document['station'], document['revision'],
        ports, response,
    )
    _checked_body(evidence)
    return evidence


def load_evidence(value: StationEvidence | str) -> StationEvidence:
    if isinstance(value, str):
        return decode_evidence(value)
    _checked_body(value)
    return value
