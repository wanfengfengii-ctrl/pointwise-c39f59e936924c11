import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from report.archive import ReportArchive
from station.freeze import freeze_station
from station.issue import export_station
from station.store import EvidenceStore
from trial.registry import register
from trial.revisions import RevisionStore
from wiring.freeze import freeze_wiring
from wiring.registry import WiringRegistry

SAMPLE_PATH = Path(__file__).resolve().parents[1] / 'sample.json'


def sample_data():
    return json.loads(SAMPLE_PATH.read_text(encoding='utf-8'))


def readings(samples):
    return tuple(sample.value for sample in samples)


class TempBench(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix='chengwan-regression-')
        self.addCleanup(temp.cleanup)
        self.source_path = Path(temp.name) / 'station.sqlite'
        self.center_path = Path(temp.name) / 'center.sqlite'
        self.sample = sample_data()
        self.trial = self.sample['trial']
        self.open_source()
        self.open_center()

    def open_source(self):
        self.source = sqlite3.connect(self.source_path)
        self.addCleanup(self.source.close)
        self.revisions = RevisionStore(self.source)
        self.evidence = EvidenceStore(self.source)
        self.revisions.initialize()
        self.evidence.initialize()

    def open_center(self):
        self.center = sqlite3.connect(self.center_path)
        self.addCleanup(self.center.close)
        self.registry = WiringRegistry(self.center)
        self.archive = ReportArchive(self.center)
        self.registry.initialize()
        self.archive.initialize()

    def station(self, data, **updates):
        entry = {**data, **updates}
        register(
            self.revisions, self.trial, entry['station'], entry['revision'], entry['model'],
            entry['initial_state'], entry['source'],
        )
        return freeze_station(self.revisions, self.evidence, self.trial, entry['station'], entry['revision'])

    def pair(self):
        return self.station(self.sample['left']), self.station(self.sample['right'])

    def wire(self, left, right, to_right='1', to_left='1'):
        self.registry.register_ports(left.ports)
        self.registry.register_ports(right.ports)
        frozen = freeze_wiring(self.registry, left.ports, right.ports, to_right, to_left)
        stored = self.registry.get_fixed(frozen.wiring_id)
        self.assertEqual(stored, frozen)
        return stored

    def export_pair(self, left, right):
        return tuple(export_station(self.evidence, evidence.evidence_id) for evidence in (left, right))

    def station_counts(self):
        return (
            self.source.execute('SELECT count(*) FROM trial_revisions').fetchone()[0],
            self.source.execute('SELECT count(*) FROM station_evidence').fetchone()[0],
        )

    def archive_counts(self):
        return (
            self.center.execute('SELECT count(*) FROM reports').fetchone()[0],
            self.center.execute('SELECT count(*) FROM issue_receipts').fetchone()[0],
        )
