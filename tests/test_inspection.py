import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from checklist import CHECKLISTS
from database import connect_database
from service import initialize_demo
from inspection import save_inspection, latest_inspection


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.connection = connect_database(Path(self.folder.name) / "test.db")
        initialize_demo(self.connection, datetime(2026, 1, 8))
        self.event = self.connection.execute("SELECT * FROM events ORDER BY id LIMIT 1").fetchone()
        self.checked = dict.fromkeys(CHECKLISTS[self.event["sensor_name"]], False)

    def tearDown(self):
        self.connection.close()
        self.folder.cleanup()

    def test_completion_validation_and_history(self):
        event_id = self.event["id"]
        with self.assertRaises(ValueError):
            save_inspection(self.connection, event_id, self.checked, "원인", "조치", "조치 완료")
        self.assertIsNone(latest_inspection(self.connection, event_id))
        first = save_inspection(self.connection, event_id, self.checked, "", "", "점검 중")
        complete = dict.fromkeys(self.checked, True)
        with self.assertRaises(ValueError):
            save_inspection(self.connection, event_id, complete, " ", "조치", "조치 완료", first)
        second = save_inspection(self.connection, event_id, complete,
                                 "원인 미확정", "점검 및 재측정 완료", "조치 완료", first)
        self.assertGreater(second, first)
        row = latest_inspection(self.connection, event_id)
        self.assertTrue(all(json.loads(row["checklist_json"]).values()))
        self.assertEqual(self.connection.execute("SELECT progress_status FROM events WHERE id=?",
                                               (event_id,)).fetchone()[0], "조치 완료")
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM inspection_records").fetchone()[0], 2)
        with self.assertRaises(ValueError):
            save_inspection(self.connection, event_id, complete, "원인", "조치", "점검 중", first)
        self.assertEqual(latest_inspection(self.connection, event_id)["id"], second)

    def test_invalid_event_and_checklist(self):
        with self.assertRaises(ValueError):
            save_inspection(self.connection, 999999, self.checked, "", "", "점검 중")
        with self.assertRaises(ValueError):
            save_inspection(self.connection, self.event["id"], {}, "", "", "점검 중")

    def test_form_rejects_record_saved_by_another_session(self):
        from streamlit.testing.v1 import AppTest

        db_path = str(Path(self.folder.name) / "test.db")
        with patch.dict(os.environ, {"SEMI_GUARD_DB": db_path}):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"),
                                    default_timeout=45).run()
            app.sidebar.radio[0].set_value("이상 이력 및 조치").run()
            event_id = next(item for item in app.selectbox if item.label == "점검할 이벤트").value
            sensor = self.connection.execute("SELECT sensor_name FROM events WHERE id=?",
                                             (int(event_id),)).fetchone()[0]
            first = save_inspection(self.connection, event_id, dict.fromkeys(CHECKLISTS[sensor], False),
                                    "다른 창의 원인", "다른 창의 기록", "점검 중")
            app.text_area[0].set_value("현재 창의 원인")
            next(item for item in app.button if item.label == "점검 기록 저장").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any("다른 창" in error.value for error in app.error))
            self.assertEqual(latest_inspection(self.connection, event_id)["id"], first)
            self.assertEqual(app.text_area[0].value, "현재 창의 원인")
            next(item for item in app.button if item.label == "최신 점검 기록 다시 불러오기").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.text_area[0].value, "다른 창의 원인")
