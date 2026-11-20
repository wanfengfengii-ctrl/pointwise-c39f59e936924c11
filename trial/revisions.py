import json
import sqlite3
from dataclasses import dataclass

from trial.cutoff import CutoffState, validate_cutoff
from trial.model import (
    PeriodicModel,
    StationModel,
    dynamics_payload,
    stages_payload,
    validate_name,
    validate_station_or_periodic,
)
from trial.rationals import format_rational


@dataclass(frozen=True, slots=True)
class TrialRevision:
    trial: str
    station: str
    revision: int
    model: StationModel | PeriodicModel
    cutoff: CutoffState


def revision_key(trial: object, station: object, revision: object) -> tuple[str, str, int]:
    trial = validate_name(trial, 'trial')
    station = validate_name(station, 'station')
    if type(revision) is not int or not 1 <= revision <= 2**63 - 1:
        raise ValueError('revision must be a positive SQLite integer')
    return trial, station, revision


class RevisionStore:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def initialize(self) -> None:
        with self._connection:
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS trial_revisions (
                    trial TEXT NOT NULL,
                    station TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    cutoff TEXT NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (trial, station, revision)
                )
            ''')

    def add(self, entry: TrialRevision) -> TrialRevision:
        key = revision_key(entry.trial, entry.station, entry.revision)
        model = validate_station_or_periodic(entry.model)
        cutoff = validate_cutoff(model, entry.cutoff.initial_state, entry.cutoff.source)
        if isinstance(model, PeriodicModel):
            model_json = json.dumps({
                'ports': model.ports,
                'stages': stages_payload(model.stages),
                'phase': model.phase,
            })
        else:
            model_json = json.dumps({'ports': model.ports, **dynamics_payload(model.dynamics)})
        state_json = json.dumps([format_rational(value) for value in cutoff.initial_state])
        with self._connection:
            result = self._connection.execute('''
                INSERT INTO trial_revisions (trial, station, revision, model, cutoff, source)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (trial, station, revision) DO NOTHING
            ''', (*key, model_json, state_json, cutoff.source))
            if result.rowcount != 1:
                raise ValueError('trial revision already exists')
        return TrialRevision(*key, model, cutoff)

    def get_exact(self, trial: str, station: str, revision: int) -> TrialRevision | None:
        key = revision_key(trial, station, revision)
        row = self._connection.execute('''
            SELECT model, cutoff, source FROM trial_revisions
            WHERE trial = ? AND station = ? AND revision = ?
        ''', key).fetchone()
        if row is None:
            return None
        model_text, state_text, source = row
        model = validate_station_or_periodic(json.loads(model_text))
        cutoff = validate_cutoff(model, json.loads(state_text), source)
        return TrialRevision(*key, model, cutoff)
