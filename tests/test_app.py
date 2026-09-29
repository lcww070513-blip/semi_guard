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
