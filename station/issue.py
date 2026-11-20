from station.codec import encode_evidence, seal_evidence
from station.envelope import StationEvidence, station_ports
from station.response import build_periodic_response, build_response
from station.store import EvidenceStore
from trial.model import PeriodicModel
from trial.revisions import TrialRevision


def issue_station(store: EvidenceStore, entry: TrialRevision) -> StationEvidence:
    ports = station_ports(entry.station, entry.model.ports)
    if isinstance(entry.model, PeriodicModel):
        response = build_periodic_response(entry.model, entry.cutoff)
    else:
        response = build_response(entry.model, entry.cutoff)
    evidence = seal_evidence(entry.trial, entry.station, entry.revision, ports, response)
    return store.publish(evidence)


def export_station(store: EvidenceStore, evidence_id: str) -> str:
    evidence = store.get(evidence_id)
    if evidence is None:
        raise KeyError(('station evidence', evidence_id))
    return encode_evidence(evidence)
