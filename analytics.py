"""이상 이벤트 집계. COUNT와 그룹화는 모두 SQLite가 수행합니다."""
from datetime import date, datetime, timedelta
from database import query_frame

MAX_RANGE_DAYS = 366


def date_bounds(start_date, end_date):
    """DB 시각은 오프셋 없는 KST 문자열입니다. 종료일 전체를 포함합니다."""
    if isinstance(start_date, datetime) or isinstance(end_date, datetime):
        raise ValueError("분석 기간에는 시각이 아닌 날짜를 선택해 주세요.")
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError("분석 시작일과 종료일을 선택해 주세요.")
    days = (end_date - start_date).days + 1
    if days <= 0:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
    if days > MAX_RANGE_DAYS:
        raise ValueError("분석 기간은 최대 366일입니다. 기간을 줄여 주세요.")
    if end_date == date.max:
        raise ValueError("종료일을 9999년 12월 30일 이전으로 선택해 주세요.")
    return (f"{start_date.isoformat()} 00:00:00",
            f"{(end_date + timedelta(days=1)).isoformat()} 00:00:00")


def daily_anomalies(connection, start_date, end_date):
    bounds = date_bounds(start_date, end_date)
    return query_frame(connection, """
        WITH RECURSIVE dates(day) AS (
            SELECT date(?)
            UNION ALL SELECT date(day, '+1 day') FROM dates
            WHERE date(day, '+1 day') < date(?)
        ), counts AS (
            SELECT substr(occurred_at, 1, 10) AS day, COUNT(*) AS event_count
            FROM events WHERE severity='이상' AND occurred_at >= ? AND occurred_at < ?
            GROUP BY substr(occurred_at, 1, 10)
        )
        SELECT dates.day, COALESCE(counts.event_count, 0) AS event_count
        FROM dates LEFT JOIN counts ON dates.day=counts.day ORDER BY dates.day
        """, bounds + bounds)


def equipment_sensor_anomalies(connection, start_date, end_date):
    bounds = date_bounds(start_date, end_date)
    return query_frame(connection, """
        WITH equipment(equipment_id) AS (VALUES ('EQ-01'), ('EQ-02'), ('EQ-03')),
        sensors(sensor_name) AS (VALUES ('temperature'), ('pressure'), ('vibration')),
        counts AS (
            SELECT equipment_id, sensor_name, COUNT(*) AS event_count
            FROM events WHERE severity='이상' AND occurred_at >= ? AND occurred_at < ?
            GROUP BY equipment_id, sensor_name
        )
        SELECT equipment.equipment_id, sensors.sensor_name,
               COALESCE(counts.event_count, 0) AS event_count
        FROM equipment CROSS JOIN sensors
        LEFT JOIN counts ON counts.equipment_id=equipment.equipment_id
                        AND counts.sensor_name=sensors.sensor_name
        ORDER BY equipment.equipment_id, sensors.sensor_name
        """, bounds)


def frequent_anomaly_types(connection, start_date, end_date):
    return query_frame(connection, """
        SELECT sensor_name, direction, COUNT(*) AS event_count
        FROM events WHERE severity='이상' AND occurred_at >= ? AND occurred_at < ?
        GROUP BY sensor_name, direction
        ORDER BY event_count DESC, sensor_name, direction
        """, date_bounds(start_date, end_date))
