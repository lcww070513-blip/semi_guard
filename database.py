"""SQLite 생성 및 연결. 연결은 호출자가 반드시 닫습니다."""
import os
import sqlite3
from pathlib import Path
import pandas as pd

DEFAULT_DB = Path(__file__).resolve().parent / "data" / "semi_guard.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS threshold_sets (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    random_seed INTEGER NOT NULL,
    baseline_start TEXT NOT NULL,
    baseline_end TEXT NOT NULL,
    generator_config_json TEXT NOT NULL,
    std_ddof INTEGER NOT NULL CHECK(std_ddof = 1)
);
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    equipment_id TEXT NOT NULL CHECK(equipment_id IN ('EQ-01','EQ-02','EQ-03')),
    data_kind TEXT NOT NULL CHECK(data_kind IN ('baseline','operation')),
    temperature REAL NOT NULL,
    pressure REAL NOT NULL,
    vibration REAL NOT NULL,
    threshold_set_id INTEGER REFERENCES threshold_sets(id),
    CHECK((data_kind = 'baseline' AND threshold_set_id IS NULL)
       OR (data_kind = 'operation' AND threshold_set_id IS NOT NULL)),
    UNIQUE(equipment_id, timestamp, data_kind)
);
CREATE TABLE IF NOT EXISTS thresholds (
    id INTEGER PRIMARY KEY,
    threshold_set_id INTEGER NOT NULL REFERENCES threshold_sets(id),
    equipment_id TEXT NOT NULL CHECK(equipment_id IN ('EQ-01','EQ-02','EQ-03')),
    sensor_name TEXT NOT NULL CHECK(sensor_name IN ('temperature','pressure','vibration')),
    sample_count INTEGER NOT NULL CHECK(sample_count >= 2),
    mean_value REAL NOT NULL,
    std_value REAL NOT NULL CHECK(std_value > 0),
    lower_2sigma REAL,
    upper_2sigma REAL NOT NULL,
    lower_3sigma REAL,
    upper_3sigma REAL NOT NULL,
    UNIQUE(threshold_set_id, equipment_id, sensor_name)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    sensor_data_id INTEGER NOT NULL REFERENCES sensor_data(id),
    threshold_id INTEGER NOT NULL REFERENCES thresholds(id),
    occurred_at TEXT NOT NULL,
    equipment_id TEXT NOT NULL,
    sensor_name TEXT NOT NULL CHECK(sensor_name IN ('temperature','pressure','vibration')),
    measured_value REAL NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('주의','이상')),
    direction TEXT NOT NULL CHECK(direction IN ('상한 초과','하한 미달')),
    limit_value REAL NOT NULL,
    deviation_value REAL NOT NULL CHECK(deviation_value > 0),
    sigma_distance REAL NOT NULL,
    reason TEXT NOT NULL,
    progress_status TEXT NOT NULL DEFAULT '미확인'
        CHECK(progress_status IN ('미확인','점검 중','조치 완료')),
    UNIQUE(equipment_id, occurred_at, sensor_name)
);
CREATE TABLE IF NOT EXISTS inspection_records (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    recorded_at TEXT NOT NULL,
    checklist_json TEXT NOT NULL,
    suspected_cause TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    progress_status TEXT NOT NULL CHECK(progress_status IN ('미확인','점검 중','조치 완료'))
);
CREATE INDEX IF NOT EXISTS idx_sensor_latest ON sensor_data(data_kind, equipment_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(occurred_at, severity);
CREATE INDEX IF NOT EXISTS idx_inspections_event ON inspection_records(event_id, id);
"""


def connect_database(path=None):
    selected = Path(path or os.environ.get("SEMI_GUARD_DB", DEFAULT_DB))
    selected.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(selected, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


def query_frame(connection, sql, parameters=()):
    return pd.read_sql_query(sql, connection, params=parameters)
