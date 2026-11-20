import sqlite3

from station.codec import decode_evidence, encode_evidence
from station.envelope import StationEvidence
from trial.model import validate_name


class EvidenceStore:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def initialize(self) -> None:
        with self._connection:
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS station_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    body TEXT NOT NULL
                )
            ''')

    def publish(self, evidence: StationEvidence) -> StationEvidence:
        serialized = encode_evidence(evidence)
        with self._connection:
            self._connection.execute('''
                INSERT INTO station_evidence (evidence_id, body) VALUES (?, ?)
                ON CONFLICT (evidence_id) DO NOTHING
            ''', (evidence.evidence_id, serialized))
            if self._stored_text(evidence.evidence_id) != serialized:
                raise ValueError('station evidence id already holds different contents')
        return evidence

    def _stored_text(self, evidence_id: str) -> str | None:
        row = self._connection.execute('''
            SELECT body FROM station_evidence WHERE evidence_id = ?
        ''', (evidence_id,)).fetchone()
        return None if row is None else row[0]

    def get(self, evidence_id: str) -> StationEvidence | None:
        serialized = self._stored_text(validate_name(evidence_id, 'evidence id'))
        if serialized is None:
            return None
        evidence = decode_evidence(serialized)
        if evidence.evidence_id != evidence_id:
            raise ValueError('stored station evidence does not match its lookup id')
        return evidence
