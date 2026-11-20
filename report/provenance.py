from dataclasses import dataclass

from analysis.closed_loop import ClosedLoop
from analysis.observation import ObservationRef
from station.envelope import PublicPort, StationEvidence


@dataclass(frozen=True, slots=True)
class StationParent:
    evidence_id: str
    trial: str
    station: str
    revision: int

    @classmethod
    def from_evidence(cls, evidence: StationEvidence) -> 'StationParent':
        return cls(evidence.evidence_id, evidence.trial, evidence.station, evidence.revision)


@dataclass(frozen=True, slots=True)
class ReportParents:
    left: StationParent
    right: StationParent
    wiring_id: str
    observation: PublicPort


def bind_parents(loop: ClosedLoop, observation: ObservationRef) -> ReportParents:
    return ReportParents(
        StationParent.from_evidence(loop.left),
        StationParent.from_evidence(loop.right),
        loop.wiring.wiring_id,
        observation.port,
    )
