from station.envelope import StationEvidence
from station.issue import issue_station
from station.store import EvidenceStore
from trial.revisions import RevisionStore


def freeze_station(
    revisions: RevisionStore,
    evidence_store: EvidenceStore,
    trial: str,
    station: str,
    revision: int,
) -> StationEvidence:
    entry = revisions.get_exact(trial, station, revision)
    if entry is None:
        raise KeyError(('trial revision', trial, station, revision))
    if (entry.trial, entry.station, entry.revision) != (trial, station, revision):
        raise ValueError('station freeze does not match the requested source revision')
    return issue_station(evidence_store, entry)
