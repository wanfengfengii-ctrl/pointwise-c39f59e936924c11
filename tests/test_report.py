import sqlite3
from fractions import Fraction

from analysis.decay import DecayVerdict
from analysis.replay import preview
from report.issue import issue_report
from report.readback import read_report
from station.envelope import PublicPort
from tests.support import TempBench, readings


class ReportTests(TempBench):
    def test_offline_wiring_pair(self):
        left, right = self.pair()
        connected = self.wire(left, right)
        disconnected = self.wire(left, right, to_left=0)
        left_text, right_text = self.export_pair(left, right)
        self.source.close()
        attempts = [
            issue_report(self.archive, right_text, left_text, wiring, left.ports[2])
            for wiring in (connected, disconnected)
        ]
        self.assertEqual(
            [report.verdict for report, _ in attempts],
            [DecayVerdict.DECAY, DecayVerdict.NO_DECAY],
            'v6.offline_wiring_pair fixed return and disconnected return produced wrong decay classifications',
        )
        for wiring, issued in zip((connected, disconnected), attempts, strict=True):
            report, receipt = issued
            self.assertEqual((report.parents.left.evidence_id, report.parents.right.evidence_id),
                             (left.evidence_id, right.evidence_id))
            self.assertEqual((report.parents.left.trial, report.parents.left.station, report.parents.left.revision),
                             (self.trial, 'A', 1))
            self.assertEqual((report.parents.right.trial, report.parents.right.station, report.parents.right.revision),
                             (self.trial, 'B', 1))
            self.assertEqual(report.parents.wiring_id, wiring.wiring_id)
            self.assertEqual(report.parents.observation, left.ports[2])
            self.assertEqual(receipt.report_id, report.report_id)
            self.assertEqual(read_report(self.archive, report.report_id), issued)
        self.assertEqual(self.archive_counts(), (2, 2))

    def test_initial_state(self):
        left, right = self.pair()
        zero = self.station(self.sample['left'], revision=2, initial_state=['0'])
        wiring = self.wire(left, right, to_left=0)
        left_text, right_text = self.export_pair(left, right)
        zero_text, _ = self.export_pair(zero, right)
        self.source.close()
        actual = [issue_report(self.archive, text, right_text, wiring, left.ports[2])[0]
                  for text in (zero_text, left_text)]
        self.assertEqual([report.verdict for report in actual], [DecayVerdict.DECAY, DecayVerdict.NO_DECAY],
                         'v6.initial_state disconnected response lost the actual cutoff state')
        self.assertEqual([report.parents.left.evidence_id for report in actual],
                         [zero.evidence_id, left.evidence_id])
        self.assertEqual(readings(preview(zero_text, right_text, wiring, left.ports[2], 4)), (0, 0, 0, 0))
        self.assertEqual(readings(preview(left_text, right_text, wiring, left.ports[2], 4)), (1, 2, 4, 8))

    def test_return_excites(self):
        left_model = {**self.sample['left']['model'], 'input_vector': [1], 'return_vector': [0],
                      'observation_feedthrough': 0}
        pulse_model = {
            'ports': ['feed', 'echo', 'meter'], 'transition': [[0]], 'input_vector': [0],
            'return_vector': [1], 'return_feedthrough': 0,
            'observation_vector': [1], 'observation_feedthrough': 0,
        }
        left = self.station(self.sample['left'], model=left_model, initial_state=[0])
        right = self.station(self.sample['right'], model=pulse_model, initial_state=[1])
        connected = self.wire(left, right)
        disconnected = self.wire(left, right, to_left=0)
        exported = self.export_pair(left, right)
        self.source.close()
        self.assertEqual(readings(preview(*exported, connected, left.ports[2], 5)), (0, 0, 1, 2, 4))
        self.assertEqual(readings(preview(*exported, connected, right.ports[2], 5)), (1, 0, 0, 0, 0))
        for wiring, port, expected in (
            (connected, left.ports[2], DecayVerdict.NO_DECAY),
            (connected, right.ports[2], DecayVerdict.DECAY),
            (disconnected, left.ports[2], DecayVerdict.DECAY),
        ):
            with self.subTest(wiring=wiring.wiring_id, port=port):
                report, _ = issue_report(self.archive, *exported, wiring, port)
                self.assertEqual(report.verdict, expected)
                self.assertEqual(report.parents.observation, port)

    def test_read_old_after_revision(self):
        left, right = self.pair()
        wiring = self.wire(left, right, to_left=0)
        old_text, right_text = self.export_pair(left, right)
        self.source.close()
        old = issue_report(self.archive, old_text, right_text, wiring, left.ports[2])
        self.open_source()
        corrected = self.station(self.sample['left'], revision=2, initial_state=['0'])
        new_text, _ = self.export_pair(corrected, right)
        self.source.close()
        new = issue_report(self.archive, new_text, right_text, wiring, left.ports[2])
        self.assertEqual((old[0].verdict, new[0].verdict), (DecayVerdict.NO_DECAY, DecayVerdict.DECAY))
        self.assertEqual((old[0].parents.left.evidence_id, new[0].parents.left.evidence_id),
                         (left.evidence_id, corrected.evidence_id))
        self.assertEqual((old[0].parents.left.revision, new[0].parents.left.revision), (1, 2))
        self.center.close()
        self.open_center()
        self.archive.initialize()
        self.registry.initialize()
        self.assertEqual(read_report(self.archive, old[0].report_id), old)
        self.assertEqual(read_report(self.archive, new[0].report_id), new)
        self.assertEqual(self.registry.get_fixed(wiring.wiring_id), wiring)
        self.assertEqual(self.archive_counts(), (2, 2))

    def test_receipt_identity(self):
        left, right = self.pair()
        connected = self.wire(left, right)
        disconnected = self.wire(left, right, to_left=0)
        exported = self.export_pair(left, right)
        first = issue_report(self.archive, *exported, connected, left.ports[2])
        second = issue_report(self.archive, *exported, disconnected, left.ports[2])
        self.assertNotEqual(first[1].receipt_id, second[1].receipt_id)
        self.station(self.sample['left'], revision=2, initial_state=[0])
        self.source.close()
        self.center.close()
        self.open_center()
        for original in (first, second):
            report, receipt = read_report(self.archive, original[0].report_id)
            self.assertEqual((report, receipt), original)
            self.assertEqual(receipt.report_id, report.report_id)

    def test_unknown_report(self):
        left, right = self.pair()
        wiring = self.wire(left, right)
        original = issue_report(self.archive, left, right, wiring, left.ports[2])
        self.assertIsNone(read_report(self.archive, original[0].report_id + 1))
        self.assertEqual(read_report(self.archive, original[0].report_id), original)
        self.assertEqual(self.archive_counts(), (1, 1))

    def test_wrong_station(self):
        left, right = self.pair()
        wrong_model = {**self.sample['right']['model'], 'ports': ['other-in', 'other-out', 'other-view']}
        wrong = self.station(self.sample['right'], station='C', model=wrong_model)
        wiring = self.wire(left, right)
        before = self.archive_counts()
        with self.assertRaisesRegex(ValueError, 'fixed wiring ports'):
            issue_report(self.archive, left, wrong, wiring, left.ports[2])
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            issue_report(self.archive, left, right, wiring, wrong.ports[2])
        self.assertEqual(self.archive_counts(), before)

    def test_shared_short_name(self):
        left, right = self.pair()
        wrong = self.station(self.sample['right'], station='C')
        wiring = self.wire(left, right)
        self.assertEqual(tuple(port.name for port in wrong.ports), tuple(port.name for port in right.ports))
        self.assertEqual(left.ports[2].name, right.ports[2].name)
        first = issue_report(self.archive, left, right, wiring, left.ports[2])
        with self.assertRaises(ValueError):
            issue_report(self.archive, left, wrong, wiring, left.ports[2])
        with self.assertRaises(ValueError):
            issue_report(self.archive, left, right, wiring, PublicPort('A', 'return', 'meter'))
        self.assertEqual(self.archive_counts(), (1, 1))
        self.assertEqual(read_report(self.archive, first[0].report_id), first)

    def test_issue_rollback(self):
        left, right = self.pair()
        connected = self.wire(left, right)
        disconnected = self.wire(left, right, to_left=0)
        exported = self.export_pair(left, right)
        first = issue_report(self.archive, *exported, connected, left.ports[2])
        self.center.executescript('''
            CREATE TABLE failure_parent (id INTEGER PRIMARY KEY);
            CREATE TABLE failure_check (
                parent_id INTEGER REFERENCES failure_parent(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TRIGGER fail_receipt_commit AFTER INSERT ON issue_receipts
            BEGIN
                INSERT INTO failure_check (parent_id) VALUES (1);
            END;
        ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY constraint failed'):
            issue_report(self.archive, *exported, disconnected, left.ports[2])
        self.assertFalse(self.center.in_transaction)
        self.assertEqual(self.archive_counts(), (1, 1))
        self.center.close()
        self.open_center()
        self.assertEqual(self.archive_counts(), (1, 1))
        self.assertEqual(read_report(self.archive, first[0].report_id), first)
        self.assertIsNone(read_report(self.archive, first[0].report_id + 1))
        self.assertEqual(self.center.execute('SELECT count(*) FROM failure_check').fetchone()[0], 0)
        self.center.execute('DROP TRIGGER fail_receipt_commit')
        new_report, new_receipt = issue_report(self.archive, *exported, disconnected, left.ports[2])
        self.assertEqual(new_report.verdict, DecayVerdict.NO_DECAY)
        self.assertEqual(new_receipt.report_id, new_report.report_id)
        self.assertEqual(self.archive_counts(), (2, 2))

    def test_unit_and_decaying_modes(self):
        right = self.station(self.sample['right'])
        base_model = self.sample['left']['model']
        for revision, factor, expected, first_four in (
            (1, '-1', DecayVerdict.NO_DECAY, (1, -1, 1, -1)),
            (2, '1/2', DecayVerdict.DECAY, (1, Fraction(1, 2), Fraction(1, 4), Fraction(1, 8))),
        ):
            with self.subTest(factor=factor):
                left = self.station(self.sample['left'], revision=revision, model={**base_model, 'transition': [[factor]]})
                disconnected = self.wire(left, right, to_left=0)
                report, _ = issue_report(self.archive, left, right, disconnected, left.ports[2])
                self.assertEqual(readings(preview(left, right, disconnected, left.ports[2], 4)), first_four)
                self.assertEqual(report.verdict, expected)

    def test_zero_and_constant(self):
        right = self.station(self.sample['right'])
        constant_model = {**self.sample['left']['model'], 'transition': [[1]]}
        zero = self.station(self.sample['left'], model=constant_model, initial_state=[0])
        constant = self.station(self.sample['left'], revision=2, model=constant_model, initial_state=[1])
        wiring = self.wire(zero, right, to_left=0)
        for left, value, verdict in ((zero, 0, DecayVerdict.DECAY), (constant, 1, DecayVerdict.NO_DECAY)):
            with self.subTest(initial=value):
                report, _ = issue_report(self.archive, left, right, wiring, left.ports[2])
                self.assertEqual(report.verdict, verdict)
                self.assertEqual(readings(preview(left, right, wiring, left.ports[2], 4)), (value,) * 4)

    def test_complex_modes(self):
        right = self.station(self.sample['right'])
        for revision, radius, verdict in ((1, 1, DecayVerdict.NO_DECAY), (2, Fraction(1, 2), DecayVerdict.DECAY)):
            model = {
                **self.sample['left']['model'], 'transition': [[0, -radius], [radius, 0]],
                'input_vector': [0, 0], 'return_vector': [1, 0], 'observation_vector': [1, 0],
            }
            with self.subTest(radius=radius):
                left = self.station(self.sample['left'], revision=revision, model=model, initial_state=[1, 0])
                wiring = self.wire(left, right, to_left=0)
                self.assertEqual(readings(preview(left, right, wiring, left.ports[2], 5)), (1, 0, -radius**2, 0, radius**4))
                report, _ = issue_report(self.archive, left, right, wiring, left.ports[2])
                self.assertEqual(report.verdict, verdict)
