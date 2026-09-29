import os
from pathlib import Path
from datetime import date, timedelta
from contextlib import closing
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def test_analysis_empty_period_and_invalid_range(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"SEMI_GUARD_DB": str(Path(folder) / "app.db")}):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=45).run()
                app.sidebar.radio[0].set_value("분석").run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.get("plotly_chart")), 2)
                app.date_input[0].set_value(date(2020, 1, 1))
                app.date_input[1].set_value(date(2020, 1, 2)).run()
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(any("이상 이벤트가 없습니다" in item.value for item in app.info))
                app.date_input[0].set_value(date(2020, 1, 3)).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 1)

    def test_refresh_does_not_insert_but_button_adds_three_rows(self):
        import sqlite3
        from config import now_kst
        with tempfile.TemporaryDirectory() as folder:
            db_path = str(Path(folder) / "app.db")
            with patch.dict(os.environ, {"SEMI_GUARD_DB": db_path}):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=45).run()
                with closing(sqlite3.connect(db_path)) as connection:
                    before = connection.execute("SELECT COUNT(*) FROM sensor_data").fetchone()[0]
                app.run()
                with closing(sqlite3.connect(db_path)) as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM sensor_data").fetchone()[0], before)
                with patch("service.now_kst", return_value=now_kst() + timedelta(seconds=5)):
                    app.sidebar.button[0].click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0)
                with closing(sqlite3.connect(db_path)) as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM sensor_data").fetchone()[0], before + 3)

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

    def test_inspection_form(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"SEMI_GUARD_DB": str(Path(folder) / "app.db")}):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=45).run()
                app.sidebar.radio[0].set_value("이상 이력 및 조치").run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.checkbox), 4)
                for checkbox in app.checkbox:
                    checkbox.check()
                app.text_area[0].set_value("학습용 원인 미확정")
                app.text_area[1].set_value("체크리스트 점검 및 재측정")
                next(item for item in app.selectbox if item.label == "저장할 진행 상태").set_value("조치 완료")
                next(item for item in app.button if item.label == "점검 기록 저장").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0)
                self.assertTrue(any("저장했습니다" in item.value for item in app.success))
