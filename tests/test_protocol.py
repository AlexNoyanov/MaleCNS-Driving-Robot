import unittest

from shared.protocol import format_motor_line, parse_motor_line, parse_sensor_line


class ProtocolTests(unittest.TestCase):
    def test_sensor_roundtrip(self):
        self.assertEqual(parse_sensor_line("S,12.4,80.1,15.2\n"), (12.4, 80.1, 15.2))
        self.assertEqual(parse_sensor_line("S,-1.0,40.0,9.5\r\n"), (-1.0, 40.0, 9.5))

    def test_sensor_reject(self):
        self.assertIsNone(parse_sensor_line("hello"))
        self.assertIsNone(parse_sensor_line("S,1,2"))

    def test_motor_format_parse(self):
        line = format_motor_line(180, -200)
        self.assertEqual(line, "M,180,-200\n")
        self.assertEqual(parse_motor_line(line), (180, -200))

    def test_motor_clip(self):
        self.assertEqual(parse_motor_line(format_motor_line(400, -400)), (255, -255))
