from dataclasses import replace
from fractions import Fraction

from analysis.replay import preview
from station.envelope import PublicPort
from tests.support import TempBench, readings
from wiring.freeze import freeze_wiring
from wiring.links import LINK_DELAY_TICKS


class ReplayTests(TempBench):
    def test_round_trip_delay(self):
        left, right = self.pair()
        wiring = self.wire(left, right)
        result = preview(left, right, wiring, left.ports[2], 4)
        self.assertEqual(tuple(item.tick for item in result), (0, 1, 2, 3))
        self.assertEqual(readings(result), (1, 2, 0, 0))
        self.assertTrue(all(isinstance(item.value, Fraction) for item in result))

    def test_disconnected_return(self):
        left, right = self.pair()
        connected = self.wire(left, right)
        broken = self.wire(left, right, to_left=0)
        self.assertNotEqual(connected.wiring_id, broken.wiring_id)
        self.assertEqual(readings(preview(*self.export_pair(left, right), broken, left.ports[2], 4)), (1, 2, 4, 8))
        self.assertEqual(readings(preview(left, right, connected, left.ports[2], 4)), (1, 2, 0, 0))

    def test_asymmetric_ports(self):
        left, right = self.pair()
        wiring = self.wire(left, right, to_right='-2', to_left='3/2')
        self.assertEqual(wiring.left_to_right.source, PublicPort('A', 'return', 'return'))
        self.assertEqual(wiring.left_to_right.destination, PublicPort('B', 'input', 'feed'))
        self.assertEqual(wiring.right_to_left.source, PublicPort('B', 'return', 'echo'))
        self.assertEqual(wiring.right_to_left.destination, PublicPort('A', 'input', 'drive'))
        self.assertEqual(readings(preview(right, left, wiring, left.ports[2], 4)), (1, 2, 16, 32))
        self.assertEqual(readings(preview(right, left, wiring, right.ports[2], 4)), (0, -2, -4, -8))

    def test_invalid_wiring(self):
        left, right = self.pair()
        self.registry.register_ports(left.ports)
        with self.assertRaises(KeyError):
            freeze_wiring(self.registry, left.ports, right.ports, 1, 1)
        original = self.wire(left, right)
        wrong_station_ports = (replace(right.ports[0], station='A'), *right.ports[1:])
        with self.assertRaises(ValueError):
            freeze_wiring(self.registry, left.ports, wrong_station_ports, 1, 1)
        with self.assertRaises(ValueError):
            freeze_wiring(self.registry, left.ports, right.ports[::-1], 1, 1)
        renamed = (replace(right.ports[0], name='unregistered'), *right.ports[1:])
        with self.assertRaises(KeyError):
            freeze_wiring(self.registry, left.ports, renamed, 1, 1)
        for illegal_gain in (None, True, 0.5, '1/0'):
            with self.subTest(gain=illegal_gain):
                with self.assertRaises(ValueError):
                    freeze_wiring(self.registry, left.ports, right.ports, 1, illegal_gain)
        self.assertEqual(self.center.execute('SELECT count(*) FROM fixed_wiring').fetchone()[0], 1)
        self.assertEqual(self.registry.get_fixed(original.wiring_id), original)

    def test_preview_boundaries(self):
        left, right = self.pair()
        wiring = self.wire(left, right)
        self.assertEqual(preview(left, right, wiring, left.ports[2], 0), ())
        for value in (-1, True, '2', 2.0):
            with self.subTest(ticks=value):
                with self.assertRaises(ValueError):
                    preview(left, right, wiring, left.ports[2], value)
        with self.assertRaises(ValueError):
            preview(left, right, wiring, PublicPort('missing', 'observation', 'meter'), 0)
        with self.assertRaises(ValueError):
            preview(right, right, wiring, right.ports[2], 0)
        altered = replace(wiring, right_to_left=replace(wiring.right_to_left, delay=0))
        with self.assertRaises(ValueError):
            preview(left, right, altered, left.ports[2], 0)

    def test_zero_return(self):
        left, right = self.pair()
        broken = self.wire(left, right, to_right='-3/2', to_left='0')
        self.center.close()
        self.open_center()
        wiring = self.registry.get_fixed(broken.wiring_id)
        self.assertEqual(wiring.left_to_right.gain, Fraction(-3, 2))
        self.assertEqual(wiring.right_to_left.gain, Fraction(0))
        self.assertEqual(wiring.right_to_left.destination, left.ports[0])
        self.assertEqual((wiring.left_to_right.delay, wiring.right_to_left.delay), (LINK_DELAY_TICKS, 1))
        self.assertEqual(readings(preview(left, right, wiring, left.ports[2], 4)), (1, 2, 4, 8))
