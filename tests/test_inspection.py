import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
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
