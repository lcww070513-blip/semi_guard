"""화면에서 사용하는 조회. 집계는 SQLite가 처리합니다."""
from database import query_frame


def latest_measurements(connection):
    return query_frame(connection, """
        SELECT s.* FROM sensor_data s
        JOIN (SELECT equipment_id, MAX(timestamp) AS latest
              FROM sensor_data WHERE data_kind='operation' GROUP BY equipment_id) m
          ON s.equipment_id=m.equipment_id AND s.timestamp=m.latest
        WHERE s.data_kind='operation' ORDER BY s.equipment_id
    """)


def event_summary(connection, today):
    return connection.execute("""
        SELECT COALESCE(SUM(CASE WHEN severity='이상' AND date(occurred_at)=?
                                THEN 1 ELSE 0 END),0) AS today_abnormal,
               COALESCE(SUM(CASE WHEN progress_status!='조치 완료' THEN 1 ELSE 0 END),0) AS unresolved
        FROM events
    """, (str(today),)).fetchone()


def recent_abnormal_events(connection):
    return query_frame(connection, """
        SELECT occurred_at AS 발생시각, equipment_id AS 설비,
               CASE sensor_name WHEN 'temperature' THEN '온도'
                    WHEN 'pressure' THEN '압력' ELSE '진동' END AS 센서,
               measured_value AS 측정값, reason AS 판정이유, progress_status AS 진행상태
        FROM events WHERE severity='이상'
        ORDER BY occurred_at DESC, id DESC LIMIT 10
    """)


def sensor_history(connection, equipment, sensor, limit=100):
    from config import SENSORS
    if sensor not in SENSORS:
        raise ValueError("지원하지 않는 센서입니다.")
    # 컬럼 이름은 위의 고정 목록으로만 허용하며, 사용자 값은 매개변수로 전달합니다.
    return query_frame(connection, f"""
        SELECT s.timestamp, s.{sensor} AS measured_value, s.threshold_set_id,
               t.mean_value,t.std_value,t.lower_2sigma,t.upper_2sigma,
               t.lower_3sigma,t.upper_3sigma
        FROM sensor_data s JOIN thresholds t
          ON t.threshold_set_id=s.threshold_set_id AND t.equipment_id=s.equipment_id
         AND t.sensor_name=?
        WHERE s.data_kind='operation' AND s.equipment_id=?
        ORDER BY s.timestamp DESC LIMIT ?
    """, (sensor, equipment, int(limit))).sort_values("timestamp")
