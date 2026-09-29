"""무작위 데이터가 아닌 직접 정한 이벤트로 SQL 집계를 검증합니다."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from database import connect_database
from analytics import daily_anomalies, equipment_sensor_anomalies, frequent_anomaly_types


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.connection = connect_database(Path(self.folder.name) / "test.db")
        self.connection.execute("INSERT INTO threshold_sets VALUES (1, '2026-01-01 00:00:00', 42, '2025-12-01', '2025-12-02', '{}', 1)")
        self.connection.execute("""INSERT INTO thresholds VALUES
            (1, 1, 'EQ-01', 'temperature', 10, 10, 1, 8, 12, 7, 13)""")

    def tearDown(self):
        self.connection.close()
        self.folder.cleanup()

    def add_event(self, timestamp, equipment='EQ-01', sensor='temperature',
                  severity='이상', direction='상한 초과'):
        data_id = self.connection.execute("""INSERT INTO sensor_data
            (timestamp, equipment_id, data_kind, temperature, pressure, vibration, threshold_set_id)
            VALUES (?, ?, 'operation', 14, 14, 14, 1)""", (timestamp, equipment)).lastrowid
        self.connection.execute("""INSERT INTO events
            (sensor_data_id, threshold_id, occurred_at, equipment_id, sensor_name,
             measured_value, severity, direction, limit_value, deviation_value, sigma_distance, reason)
            VALUES (?, 1, ?, ?, ?, 14, ?, ?, 13, 1, 4, '테스트')""",
            (data_id, timestamp, equipment, sensor, severity, direction))

    def test_known_counts_and_inclusive_kst_boundaries(self):
        self.add_event('2026-01-01 23:59:59')  # 시작일 직전: 제외
        self.add_event('2026-01-02 00:00:00')  # 시작 순간: 포함
        self.add_event('2026-01-02 12:00:00')
        self.add_event('2026-01-02 13:00:00', severity='주의')  # 제외
        self.add_event('2026-01-04 23:59:59', 'EQ-02', 'pressure', direction='하한 미달')
        self.add_event('2026-01-05 00:00:00')  # 종료일 다음 자정: 제외
        start, end = date(2026, 1, 2), date(2026, 1, 4)
        daily = daily_anomalies(self.connection, start, end)
        self.assertEqual(daily.day.tolist(), ['2026-01-02', '2026-01-03', '2026-01-04'])
        self.assertEqual(daily.event_count.tolist(), [2, 0, 1])
        heatmap = equipment_sensor_anomalies(self.connection, start, end)
        self.assertEqual(len(heatmap), 9)
        counts = heatmap.set_index(['equipment_id', 'sensor_name']).event_count.to_dict()
        self.assertEqual(counts[('EQ-01', 'temperature')], 2)
        self.assertEqual(counts[('EQ-02', 'pressure')], 1)
        self.assertEqual(counts[('EQ-03', 'vibration')], 0)
        self.assertEqual(sum(counts.values()), 3)
        types = frequent_anomaly_types(self.connection, start, end)
        self.assertEqual(types.to_dict('records'), [
            {'sensor_name': 'temperature', 'direction': '상한 초과', 'event_count': 2},
            {'sensor_name': 'pressure', 'direction': '하한 미달', 'event_count': 1}])

    def test_empty_database_and_same_day(self):
        day = date(2026, 1, 2)
        self.assertEqual(daily_anomalies(self.connection, day, day).event_count.tolist(), [0])
        heatmap = equipment_sensor_anomalies(self.connection, day, day)
        self.assertEqual(len(heatmap), 9)
        self.assertTrue((heatmap.event_count == 0).all())
        self.assertTrue(frequent_anomaly_types(self.connection, day, day).empty)

    def test_invalid_ranges(self):
        for query in (daily_anomalies, equipment_sensor_anomalies, frequent_anomaly_types):
            with self.subTest(query=query.__name__):
                with self.assertRaisesRegex(ValueError, '종료일'):
                    query(self.connection, date(2026, 1, 3), date(2026, 1, 2))
                with self.assertRaisesRegex(ValueError, '366'):
                    query(self.connection, date(2025, 1, 1), date(2026, 1, 2))
