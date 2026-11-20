import json
from fractions import Fraction

from station.codec import decode_evidence, encode_evidence
from station.freeze import freeze_station
from station.issue import export_station
from station.response import advance_state, public_output
from tests.support import TempBench


class StationTests(TempBench):
    def test_freeze_revision(self):
        left, right = self.pair()
        corrected = self.station(self.sample['left'], revision=2, initial_state=['3/2'], source='甲站另一停激记录')
        self.assertNotEqual(left.evidence_id, corrected.evidence_id)
        self.assertEqual((left.revision, corrected.revision, right.revision), (1, 2, 1))
        self.assertEqual(left.response.initial_state, (1,))
        self.assertEqual(corrected.response.initial_state, (Fraction(3, 2),))
        self.assertEqual(self.evidence.get(left.evidence_id), left)
        self.assertEqual(self.evidence.get(right.evidence_id), right)
        self.assertEqual(freeze_station(self.revisions, self.evidence, self.trial, 'A', 2), corrected)
        self.assertEqual(self.station_counts(), (3, 3))

    def test_fixed_roundtrip(self):
        entry = self.sample['left']
        old = self.station(entry, initial_state=['6/8'])
        before = export_station(self.evidence, old.evidence_id)
        self.assertEqual(json.loads(before)['version'], 1)
        self.assertEqual(json.loads(before)['response']['initial_state'], ['3/4'])
        self.assertEqual(decode_evidence(before), old)
        self.assertEqual(encode_evidence(decode_evidence(before)), before)
        self.assertNotIn(entry['source'], json.dumps(json.loads(before), ensure_ascii=False))
        self.assertNotIn('A-9', before)
        self.assertEqual(self.revisions.get_exact(self.trial, 'A', 1).cutoff.source, entry['source'])
        self.source.close()
        self.open_source()
        self.station(entry, revision=2, initial_state=['0'])
        self.assertEqual(export_station(self.evidence, old.evidence_id), before)
        with self.assertRaises(KeyError):
            export_station(self.evidence, 'missing-evidence')

    def test_public_response(self):
        model = {
            'ports': ['drive', 'return', 'meter'],
            'transition': [[2]],
            'input_vector': [3],
            'return_vector': [5],
            'return_feedthrough': -2,
            'observation_vector': [-1],
            'observation_feedthrough': 4,
        }
        evidence = self.station(self.sample['left'], model=model, initial_state=[1])
        exported = export_station(self.evidence, evidence.evidence_id)
        self.source.close()
        response = decode_evidence(exported).response
        state = response.initial_state
        outputs = []
        for value in map(Fraction, (2, -1, 0)):
            outputs.append(public_output(response, state, value))
            state = advance_state(response, state, value)
        self.assertEqual(outputs, [(1, 7), (42, -12), (65, -13)])
        self.assertEqual(state, (26,))

    def test_invalid_envelope(self):
        left, _ = self.pair()
        exported = export_station(self.evidence, left.evidence_id)
        for alteration in ('version', 'length', 'station', 'changed-response', 'float'):
            with self.subTest(alteration=alteration):
                record = json.loads(exported)
                if alteration == 'version':
                    record['version'] = True
                elif alteration == 'length':
                    record['response']['initial_state'].append('0')
                elif alteration == 'station':
                    record['ports'][0]['station'] = 'B'
                elif alteration == 'changed-response':
                    record['response']['initial_state'] = ['0']
                else:
                    record['response']['dynamics']['return_feedthrough'] = 0.0
                with self.assertRaises(ValueError):
                    decode_evidence(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            decode_evidence(exported[:-1] + ',"version":1}')

    def test_missing_revision(self):
        with self.assertRaises(KeyError):
            freeze_station(self.revisions, self.evidence, self.trial, 'A', 1)
        self.assertEqual(self.station_counts(), (0, 0))

    def test_same_station_missing(self):
        original = self.station(self.sample['left'])
        for trial, station, revision in ((self.trial, 'A', 2), ('other-trial', 'A', 1), (self.trial, 'B', 1)):
            with self.subTest(trial=trial, station=station, revision=revision):
                with self.assertRaises(KeyError):
                    freeze_station(self.revisions, self.evidence, trial, station, revision)
        self.assertEqual(self.station_counts(), (1, 1))
        self.assertEqual(freeze_station(self.revisions, self.evidence, self.trial, 'A', 1), original)
