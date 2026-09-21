import unittest
import pandas as pd
from data_generator import generate_data


class GeneratorTests(unittest.TestCase):
    def test_reproducible_and_shape(self):
        first = generate_data("2026-01-01", count=100)
        pd.testing.assert_frame_equal(first, generate_data("2026-01-01", count=100))
        self.assertEqual(len(first), 300)
        self.assertEqual(set(first.equipment_id), {"EQ-01", "EQ-02", "EQ-03"})
        self.assertFalse(first.isna().any().any())
        self.assertFalse(first.equals(generate_data("2026-01-01", count=100, seed=43)))

    def test_invalid_parameters(self):
        for arguments in [{"count": 0}, {"warning_probability": .9, "abnormal_probability": .2},
                          {"warning_probability": float("nan")}, {"data_kind": "wrong"}]:
            with self.assertRaises(ValueError):
                generate_data("2026-01-01", **arguments)
