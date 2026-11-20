from dataclasses import dataclass

from station.codec import load_evidence
from station.envelope import PublicPort, StationEvidence
from wiring.registry import WiringRevision


@dataclass(frozen=True, slots=True)
class ReportRequest:
    first: StationEvidence
    second: StationEvidence
    wiring: WiringRevision
    observation: PublicPort


def normalize_request(
    first: StationEvidence | str,
    second: StationEvidence | str,
    wiring: WiringRevision,
    observation: PublicPort,
) -> ReportRequest:
    if not isinstance(wiring, WiringRevision):
        raise ValueError('report request requires a fixed wiring revision')
    if not isinstance(observation, PublicPort):
        raise ValueError('report request requires a complete observation port identity')
    return ReportRequest(load_evidence(first), load_evidence(second), wiring, observation)
