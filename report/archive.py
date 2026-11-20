import json
import sqlite3
from dataclasses import asdict, dataclass

from analysis.decay import DecayVerdict
from report.provenance import ReportParents, StationParent
from station.envelope import PublicPort


@dataclass(frozen=True, slots=True)
class ReportRecord:
    report_id: int
    parents: ReportParents
    verdict: DecayVerdict


@dataclass(frozen=True, slots=True)
class IssueReceipt:
    receipt_id: int
    report_id: int


def _parents_from_json(body: str) -> ReportParents:
    payload = json.loads(body)
    return ReportParents(
        StationParent(**payload['left']),
        StationParent(**payload['right']),
        payload['wiring_id'],
        PublicPort(**payload['observation']),
    )


class ReportArchive:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def initialize(self) -> None:
        self._connection.execute('PRAGMA foreign_keys = ON')
        with self._connection:
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    report_id INTEGER PRIMARY KEY,
                    parents TEXT NOT NULL,
                    verdict TEXT NOT NULL CHECK (verdict IN ('decay', 'no_decay'))
                )
            ''')
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS issue_receipts (
                    receipt_id INTEGER PRIMARY KEY,
                    report_id INTEGER NOT NULL UNIQUE REFERENCES reports (report_id)
                )
            ''')

    def publish(self, parents: ReportParents, verdict: DecayVerdict) -> tuple[ReportRecord, IssueReceipt]:
        if not isinstance(parents, ReportParents) or not isinstance(verdict, DecayVerdict):
            raise ValueError('report draft requires bound parents and a decay verdict')
        payload = json.dumps(asdict(parents), sort_keys=True, separators=(',', ':'))
        # Enter the connection context after BEGIN so a rejected BEGIN cannot roll back caller work.
        self._connection.execute('BEGIN IMMEDIATE')
        with self._connection:
            report = self._connection.execute('''
                INSERT INTO reports (parents, verdict) VALUES (?, ?)
            ''', (payload, verdict.value))
            report_id = report.lastrowid
            receipt = self._connection.execute('''
                INSERT INTO issue_receipts (report_id) VALUES (?)
            ''', (report_id,))
            receipt_id = receipt.lastrowid
        return ReportRecord(report_id, parents, verdict), IssueReceipt(receipt_id, report_id)

    def get(self, report_id: int) -> tuple[ReportRecord, IssueReceipt] | None:
        if type(report_id) is not int or not 1 <= report_id <= 2**63 - 1:
            raise ValueError('report id must be a positive SQLite integer')
        row = self._connection.execute('''
            SELECT report.parents, report.verdict, receipt.receipt_id, receipt.report_id
            FROM reports AS report
            JOIN issue_receipts AS receipt ON receipt.report_id = report.report_id
            WHERE report.report_id = ?
        ''', (report_id,)).fetchone()
        if row is None:
            return None
        parents, verdict, receipt_id, receipt_report_id = row
        return (
            ReportRecord(report_id, _parents_from_json(parents), DecayVerdict(verdict)),
            IssueReceipt(receipt_id, receipt_report_id),
        )
