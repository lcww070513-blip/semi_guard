import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def test_dashboard_and_detail(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"SEMI_GUARD_DB": str(Path(folder) / "app.db")}):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=45).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0)
                self.assertEqual(app.metric[0].value, "3")
                app.sidebar.radio[0].set_value("설비 상세").run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0)
                app.selectbox[0].set_value("EQ-03").run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.get("plotly_chart")), 3)
