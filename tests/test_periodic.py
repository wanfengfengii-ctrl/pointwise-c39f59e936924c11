import json
import sqlite3
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from analysis.decay import DecayVerdict
from analysis.replay import preview
from report.issue import issue_report
from report.readback import read_report
from station.codec import decode_evidence, encode_evidence
from station.envelope import PublicPort
from station.freeze import freeze_station
from station.issue import export_station
from tests.support import TempBench, readings
from trial.registry import register

PERIODIC_PATH = Path(__file__).resolve().parents[1] / 'periodic-sample.json'


def periodic_cases():
    return json.loads(PERIODIC_PATH.read_text(encoding='utf-8'))['cases']


class PeriodicBench(TempBench):
    """Extend the bench with the periodic sample inputs and their corrections."""

    def periodic_case(self, case_id):
        return next(case for case in periodic_cases() if case['trial'] == case_id)

    def _periodic_station(self, trial, entry):
        register(
            self.revisions, trial, entry['station'], entry['revision'], entry['model'],
            entry['initial_state'], entry['source'],
        )
        return freeze_station(self.revisions, self.evidence, trial, entry['station'], entry['revision'])

    def corrected_right(self, case):
        correction = case.get('right_correction')
        if correction is None:
            return None
        entry = dict(case['right'])
        entry['revision'] = correction['revision']
        entry['source'] = correction['source']
        entry['model'] = {**entry['model'], 'phase': correction['phase']}
        return self._periodic_station(case['trial'], entry)

    def public_observation(self, left, right, triple):
        station, purpose, name = triple
        target = left if left.station == station else right
        for port in target.ports:
            if port.purpose == purpose and port.name == name:
                return port
        raise AssertionError('observation port not found')

    def case_pair_and_wiring(self, case):
        left = self._periodic_station(case['trial'], case['left'])
        right = self._periodic_station(case['trial'], case['right'])
        self.registry.register_ports(left.ports)
        self.registry.register_ports(right.ports)
        wiring = self.wire(left, right, str(case['gains'][0]), str(case['gains'][1]))
        observation = self.public_observation(left, right, case['observation'])
        return left, right, wiring, observation


class PeriodicStationTests(PeriodicBench):
    def test_freeze_v2_envelope(self):
        case = self.periodic_case('CW-phase-01')
        left = self._periodic_station(case['trial'], case['left'])
        text = export_station(self.evidence, left.evidence_id)
        body = json.loads(text)
        self.assertEqual(body['version'], 2)
        self.assertEqual(sorted(body['response']), ['initial_state', 'phase', 'stages'])
        self.assertEqual(body['response']['phase'], 0)
        self.assertEqual(len(body['response']['stages']), 2)
        self.assertEqual(decode_evidence(text), left)
        self.assertEqual(encode_evidence(decode_evidence(text)), text)
        self.assertNotIn(case['left']['source'], text)

    def test_same_content_same_id(self):
        case = self.periodic_case('CW-phase-01')
        entry = case['left']
        self._periodic_station(case['trial'], entry)
        first = freeze_station(self.revisions, self.evidence, case['trial'], 'A', 1)
        second = freeze_station(self.revisions, self.evidence, case['trial'], 'A', 1)
        self.assertEqual(first.evidence_id, second.evidence_id)
        self.assertEqual(self.station_counts(), (1, 1))

    def test_revision_keeps_old_export_and_refreezes(self):
        case = self.periodic_case('CW-phase-01')
        left = self._periodic_station(case['trial'], case['left'])
        before = export_station(self.evidence, left.evidence_id)
        correction = case['right_correction']
        changed = {**case['right'], 'revision': correction['revision'], 'source': correction['source'],
                   'model': {**case['right']['model'], 'phase': correction['phase']}}
        self._periodic_station(case['trial'], changed)
        self.assertEqual(export_station(self.evidence, left.evidence_id), before)
        self.assertEqual(freeze_station(self.revisions, self.evidence, case['trial'], 'A', 1), left)
        with self.assertRaises(KeyError):
            export_station(self.evidence, 'E-missing')
        with self.assertRaises(KeyError):
            freeze_station(self.revisions, self.evidence, case['trial'], 'A', 9)

    def test_phase_or_stage_change_needs_revision(self):
        case = self.periodic_case('CW-phase-01')
        self._periodic_station(case['trial'], case['left'])
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self._periodic_station(case['trial'], {**case['left'], 'model': {**case['left']['model'], 'phase': 1}})
        self.assertEqual(self.station_counts(), (1, 1))

    def test_invalid_periodic_models(self):
        base = self.periodic_case('CW-phase-02')['right']['model']
        problems = {
            'phase-bool': {**base, 'phase': True},
            'phase-range': {**base, 'phase': 3},
            'phase-negative': {**base, 'phase': -1},
            'no-stages': {'ports': ['a', 'b', 'c'], 'phase': 0, 'stages': []},
            'too-many': {'ports': ['a', 'b', 'c'], 'phase': 0, 'stages': [base['stages'][0]] * 4},
            'missing-phase': {'ports': ['a', 'b', 'c'], 'stages': [base['stages'][0]]},
            'extra-field': {**base, 'ports': ['a', 'b', 'c'], 'dynamics': base['stages'][0]},
        }
        for label, model in problems.items():
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    register(self.revisions, 'T', 'A', 1, model, [], 'source')
        self.assertEqual(self.station_counts(), (0, 0))

    def test_stage_coordinate_mismatch(self):
        model = self.periodic_case('CW-phase-01')['left']['model']
        mismatched = {
            **model,
            'stages': [
                model['stages'][0],
                {**model['stages'][1], 'transition': [], 'input_vector': [], 'return_vector': [],
                 'observation_vector': []},
            ],
        }
        with self.assertRaisesRegex(ValueError, 'same state coordinates'):
            register(self.revisions, 'T', 'A', 1, mismatched, [1], 'source')


class PeriodicReplayTests(PeriodicBench):
    def test_case_readings_and_verdicts(self):
        for case in periodic_cases():
            left, right, wiring, observation = self.case_pair_and_wiring(case)
            corrected = self.corrected_right(case)
            for check in case['checks']:
                with self.subTest(trial=case['trial'], revision=check['right_revision']):
                    right_text = export_station(
                        self.evidence,
                        (corrected if check['right_revision'] == 2 else right).evidence_id,
                    )
                    samples = preview(export_station(self.evidence, left.evidence_id), right_text,
                                      wiring, observation, len(check['values']))
                    self.assertEqual([str(sample.value) for sample in samples], check['values'])
                    self.assertTrue(all(isinstance(sample.value, Fraction) for sample in samples))
                    report, receipt = issue_report(
                        self.archive, export_station(self.evidence, left.evidence_id),
                        right_text, wiring, observation,
                    )
                    self.assertEqual(report.verdict.value, check['verdict'])
                    self.assertEqual(receipt.report_id, report.report_id)
                    self.assertEqual(read_report(self.archive, report.report_id), (report, receipt))

    def test_periodic_cross_boundary(self):
        case = self.periodic_case('CW-phase-02')
        left, right, wiring, observation = self.case_pair_and_wiring(case)
        values = readings(preview(left, right, wiring, observation, 13))
        self.assertEqual(values[6], 1)
        self.assertEqual(values[12], 1)
        self.assertTrue(all(value == 0 for index, value in enumerate(values) if index not in (6, 12)))
        report, _ = issue_report(self.archive, left, right, wiring, observation)
        self.assertEqual(report.verdict, DecayVerdict.NO_DECAY)

    def test_window_does_not_limit_verdict(self):
        case = self.periodic_case('CW-phase-02')
        left, right, wiring, observation = self.case_pair_and_wiring(case)
        short = preview(left, right, wiring, observation, 3)
        self.assertEqual(readings(short), (0, 0, 0))
        report, _ = issue_report(self.archive, left, right, wiring, observation)
        self.assertEqual(report.verdict, DecayVerdict.NO_DECAY)

    def test_swapped_order_and_exports(self):
        case = self.periodic_case('CW-phase-01')
        left, right, wiring, observation = self.case_pair_and_wiring(case)
        corrected = self.corrected_right(case)
        left_text = export_station(self.evidence, left.evidence_id)
        right_text = export_station(self.evidence, corrected.evidence_id)
        self.assertEqual(
            readings(preview(right_text, left_text, wiring, observation, 4)),
            readings(preview(left_text, right_text, wiring, observation, 4)),
        )
        report, receipt = issue_report(self.archive, right_text, left_text, wiring, observation)
        self.assertEqual((report.parents.left.evidence_id, report.parents.right.evidence_id),
                         (left.evidence_id, corrected.evidence_id))
        self.assertEqual(report.verdict, DecayVerdict.DECAY)
        self.assertEqual(read_report(self.archive, report.report_id), (report, receipt))

    def test_v2_one_stage_matches_v1(self):
        sample = self.sample
        periodic_left = {
            'station': sample['left']['station'], 'revision': 1, 'initial_state': sample['left']['initial_state'],
            'source': 'rewrapped', 'model': {'ports': sample['left']['model']['ports'], 'phase': 0,
                                             'stages': [{key: value for key, value in sample['left']['model'].items()
                                                         if key != 'ports'}]},
        }
        periodic_right = {
            'station': sample['right']['station'], 'revision': 1,
            'initial_state': sample['right']['initial_state'], 'source': 'rewrapped',
            'model': {'ports': sample['right']['model']['ports'], 'phase': 0,
                      'stages': [{key: value for key, value in sample['right']['model'].items()
                                  if key != 'ports'}]},
        }
        left = self._periodic_station(sample['trial'], periodic_left)
        right = self._periodic_station(sample['trial'], periodic_right)
        self.assertEqual(json.loads(export_station(self.evidence, left.evidence_id))['version'], 2)
        self.registry.register_ports(left.ports)
        self.registry.register_ports(right.ports)
        connected = self.wire(left, right, '1', '1')
        broken = self.wire(left, right, '1', '0')
        self.assertEqual(readings(preview(left, right, connected, left.ports[2], 4)), (1, 2, 0, 0))
        self.assertEqual(readings(preview(left, right, broken, left.ports[2], 4)), (1, 2, 4, 8))
        verdicts = [
            issue_report(self.archive, left, right, wiring, left.ports[2])[0].verdict
            for wiring in (connected, broken)
        ]
        self.assertEqual(verdicts, [DecayVerdict.DECAY, DecayVerdict.NO_DECAY])


class PeriodicRejectionTests(PeriodicBench):
    def test_bad_artifact_rejected(self):
        case = self.periodic_case('CW-phase-01')
        left = self._periodic_station(case['trial'], case['left'])
        text = export_station(self.evidence, left.evidence_id)
        document = json.loads(text)
        for label, mutate, message in (
            ('id', lambda body: body.update(evidence_id='E-deadbeef'), 'fixed contents'),
            ('phase', lambda body: body['response'].update(phase=1), 'fixed contents'),
            ('version', lambda body: body.update(version=True), 'version'),
            ('stage-length', lambda body: body['response']['stages'].append(body['response']['stages'][0]),
             'fixed contents'),
        ):
            with self.subTest(label=label):
                body = json.loads(text)
                mutate(body)
                with self.assertRaisesRegex(ValueError, message):
                    decode_evidence(json.dumps(body))
        with self.assertRaisesRegex(ValueError, 'declared version'):
            decode_evidence(json.dumps({**document, 'version': 2,
                                        'response': {'dynamics': document['response']['stages'][0],
                                                     'initial_state': []}}))

    def test_mixed_version_and_trial(self):
        phase_case = self.periodic_case('CW-phase-01')
        p_left, p_right, wiring, observation = self.case_pair_and_wiring(phase_case)
        v1_left = self.station(self.sample['left'])
        with self.assertRaisesRegex(ValueError, 'same evidence version'):
            preview(p_left, v1_left, wiring, p_left.ports[2], 1)
        other_trial = self._periodic_station('CW-phase-other', phase_case['right'])
        self.registry.register_ports(other_trial.ports)
        with self.assertRaisesRegex(ValueError, 'same trial'):
            preview(p_left, other_trial, wiring, p_left.ports[2], 1)

    def test_wrong_pair_and_observation(self):
        case = self.periodic_case('CW-phase-01')
        left, right, wiring, _ = self.case_pair_and_wiring(case)
        outsider = self._periodic_station(case['trial'], {**case['right'], 'station': 'C'})
        self.registry.register_ports(outsider.ports)
        with self.assertRaisesRegex(ValueError, 'fixed wiring ports'):
            preview(left, outsider, wiring, left.ports[2], 1)
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            preview(left, right, wiring, PublicPort('C', 'observation', 'meter'), 1)
        with self.assertRaises(ValueError):
            preview(left, right, replace(wiring, right_to_left=replace(wiring.right_to_left, delay=0)),
                    left.ports[2], 0)

    def test_commit_failure_rolls_back_v2(self):
        case = self.periodic_case('CW-phase-01')
        left, right, wiring, observation = self.case_pair_and_wiring(case)
        corrected = self.corrected_right(case)
        first = issue_report(self.archive, left, right, wiring, observation)
        corrected_text = export_station(self.evidence, corrected.evidence_id)
        left_text = export_station(self.evidence, left.evidence_id)
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
            issue_report(self.archive, left_text, corrected_text, wiring, observation)
        self.assertFalse(self.center.in_transaction)
        self.assertEqual(self.archive_counts(), (1, 1))
        self.center.execute('DROP TRIGGER fail_receipt_commit')
        new_report, new_receipt = issue_report(self.archive, left_text, corrected_text, wiring, observation)
        self.assertEqual(new_report.verdict, DecayVerdict.DECAY)
        self.assertEqual(read_report(self.archive, first[0].report_id), first)
        self.assertEqual(read_report(self.archive, new_report.report_id), (new_report, new_receipt))
        self.assertEqual(self.archive_counts(), (2, 2))

    def test_closed_station_reopen_readback(self):
        case = self.periodic_case('CW-phase-01')
        left, right, wiring, observation = self.case_pair_and_wiring(case)
        left_text = export_station(self.evidence, left.evidence_id)
        right_text = export_station(self.evidence, right.evidence_id)
        original = issue_report(self.archive, left_text, right_text, wiring, observation)
        self.assertEqual(original[0].verdict, DecayVerdict.NO_DECAY)
        self.source.close()
        self.center.close()
        self.open_center()
        self.assertEqual(read_report(self.archive, original[0].report_id), original)
        self.assertEqual(self.registry.get_fixed(wiring.wiring_id), wiring)
