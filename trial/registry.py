from trial.cutoff import validate_cutoff
from trial.model import validate_station_or_periodic
from trial.revisions import RevisionStore, TrialRevision, revision_key


def register(
    store: RevisionStore,
    trial: str,
    station: str,
    revision: int,
    model: object,
    initial_state: object,
    source: str,
) -> TrialRevision:
    key = revision_key(trial, station, revision)
    station_model = validate_station_or_periodic(model)
    cutoff = validate_cutoff(station_model, initial_state, source)
    return store.add(TrialRevision(*key, station_model, cutoff))
