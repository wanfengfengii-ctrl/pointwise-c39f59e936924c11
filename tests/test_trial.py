from station.freeze import freeze_station
from tests.support import TempBench
from trial.registry import register
from trial.rationals import format_rational, parse_rational


class TrialTests(TempBench):
    def test_invalid_cutoff(self):
        base = self.station(self.sample['left'])
        with self.assertRaisesRegex(ValueError, 'cutoff state'):
            self.station(self.sample['left'], revision=2, initial_state=[])
        self.assertEqual(self.station_counts(), (1, 1))
        self.assertIsNone(self.revisions.get_exact(self.trial, 'A', 2))
        self.assertEqual(freeze_station(self.revisions, self.evidence, self.trial, 'A', 1), base)

    def test_overlong_state(self):
        base = self.station(self.sample['left'])
        with self.assertRaisesRegex(ValueError, 'exactly 1 entries'):
            self.station(self.sample['left'], revision=2, initial_state=['1', '2'])
        self.assertIsNone(self.revisions.get_exact(self.trial, 'A', 2))
        self.assertEqual(self.station_counts(), (1, 1))
        self.assertEqual(freeze_station(self.revisions, self.evidence, self.trial, 'A', 1), base)

    def test_invalid_rational(self):
        base = self.station(self.sample['left'])
        left_model = self.sample['left']['model']
        for value in (0.5, False, None, '1/0', '1.0', ''):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.station(self.sample['left'], revision=2, initial_state=[value])
                invalid_model = {**left_model, 'transition': [[value]]}
                with self.assertRaises(ValueError):
                    self.station(self.sample['left'], revision=2, model=invalid_model)
        self.assertEqual(format_rational(parse_rational('+6/8')), '3/4')
        self.assertEqual(self.station_counts(), (1, 1))
        self.assertEqual(self.evidence.get(base.evidence_id), base)

    def test_duplicate_identity_preserves_original(self):
        base = self.station(self.sample['left'])
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.station(self.sample['left'], initial_state=['3'])
        with self.assertRaises(ValueError):
            register(self.revisions, self.trial, '', 2, self.sample['left']['model'], ['1'], 'source')
        with self.assertRaises(ValueError):
            self.station(self.sample['left'], revision=True)
        self.assertEqual(self.revisions.get_exact(self.trial, 'A', 1).cutoff.initial_state, (1,))
        self.assertEqual(self.evidence.get(base.evidence_id), base)
        self.assertEqual(self.station_counts(), (1, 1))
