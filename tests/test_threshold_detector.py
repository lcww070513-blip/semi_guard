import math
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from data_generator import generate_data
from threshold import calculate_thresholds, save_thresholds
from detector import detect_sensor, detect_equipment
from database import connect_database
from service import initialize_demo, save_measurements, get_threshold_map


def sample_threshold(sensor="temperature"):
    return {"mean_value": 10.0, "std_value": 2.0,
            "lower_2sigma": None if sensor == "vibration" else 6.0,
            "upper_2sigma": 14.0,
            "lower_3sigma": None if sensor == "vibration" else 4.0,
            "upper_3sigma": 16.0}


class ThresholdDetectorTests(unittest.TestCase):
    def test_two_sided_boundaries(self):
        cases = [(6, "정상"), (14, "정상"), (4, "주의"), (16, "주의"),
                 (math.nextafter(4, -math.inf), "이상"),
                 (math.nextafter(16, math.inf), "이상"),
                 (math.nextafter(6, -math.inf), "주의"),
                 (math.nextafter(14, math.inf), "주의")]
        for sensor in ("temperature", "pressure"):
            for value, expected in cases:
                with self.subTest(sensor=sensor, value=value):
                    self.assertEqual(detect_sensor(sensor, value, sample_threshold())["severity"], expected)

    def test_vibration_upper_only(self):
        for value, expected in [(-100, "정상"), (14, "정상"), (16, "주의"), (17, "이상")]:
            self.assertEqual(detect_sensor("vibration", value, sample_threshold("vibration"))["severity"], expected)

    def test_priority_and_reason(self):
        thresholds = {s: sample_threshold(s) for s in ("temperature", "pressure", "vibration")}
        result = detect_equipment({"temperature": 15, "pressure": 3, "vibration": 10}, thresholds)
        self.assertEqual(result["status"], "이상")
        event = result["sensors"][1]
        self.assertEqual(event["deviation_value"], 1)
        self.assertEqual(event["limit_value"], 4)
        self.assertEqual(event["direction"], "하한 미달")
        self.assertIn("3σ", event["reason"])
        self.assertEqual(len(result["reasons"]), 2)

    def test_statistics(self):
        frame = generate_data("2026-01-01", count=3, data_kind="baseline")
        frame["temperature"] = [1, 1, 1, 2, 2, 2, 3, 3, 3]
        rows = calculate_thresholds(frame)
        self.assertEqual(len(rows), 9)
        temperature = next(r for r in rows if r["sensor_name"] == "temperature")
        self.assertEqual(temperature["mean_value"], 2)
        self.assertEqual(temperature["std_value"], 1)
        vibration = next(r for r in rows if r["sensor_name"] == "vibration")
        self.assertIsNone(vibration["lower_2sigma"])

    def test_invalid_baseline(self):
        for count in [1, 3]:
            frame = generate_data("2026-01-01", count=count, data_kind="baseline")
            frame["temperature"] = 1
            with self.assertRaises(ValueError):
                calculate_thresholds(frame)
        frame = generate_data("2026-01-01", count=3, data_kind="baseline")
        frame.loc[0, "pressure"] = float("nan")
        with self.assertRaises(ValueError):
            calculate_thresholds(frame)
        with self.assertRaises(ValueError):
            detect_sensor("temperature", float("inf"), sample_threshold())

    def test_initialization_and_duplicate_events(self):
        with tempfile.TemporaryDirectory() as folder:
            connection = connect_database(Path(folder) / "test.db")
            try:
                self.assertTrue(initialize_demo(connection, datetime(2026, 1, 8, 12)))
                self.assertFalse(initialize_demo(connection, datetime(2026, 1, 8, 12)))
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM thresholds").fetchone()[0], 9)
                frame = generate_data("2026-01-09", count=1)
                limits = get_threshold_map(connection, 1, "EQ-01")
                frame.loc[frame.equipment_id == "EQ-01", "temperature"] = limits["temperature"]["upper_3sigma"] + 1
                with connection:
                    self.assertEqual(save_measurements(connection, frame, 1), 3)
                event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                with connection:
                    self.assertEqual(save_measurements(connection, frame, 1), 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], event_count)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                connection.close()
