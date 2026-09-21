"""데이터 생성 → 기준 산출 → 판정 → 저장을 하나의 흐름으로 연결합니다."""
from datetime import timedelta
from data_generator import generate_data, PROFILES
from threshold import save_thresholds
from detector import detect_equipment
from config import now_kst


def get_threshold_map(connection, set_id, equipment_id):
    rows = connection.execute(
        "SELECT * FROM thresholds WHERE threshold_set_id=? AND equipment_id=?",
        (int(set_id), equipment_id)).fetchall()
    result = {row["sensor_name"]: dict(row) for row in rows}
    if len(result) != 3:
        raise ValueError("설비의 센서 기준이 완전하지 않습니다. 기준 데이터를 확인하세요.")
    return result


def save_measurements(connection, frame, set_id=None):
    saved_count = 0
    threshold_cache = {}
    for row in frame.to_dict("records"):
        kind = row["data_kind"]
        if kind == "operation":
            if set_id is None:
                raise ValueError("운영 데이터에는 판정 기준이 필요합니다.")
            equipment = row["equipment_id"]
            if equipment not in threshold_cache:
                threshold_cache[equipment] = get_threshold_map(connection, set_id, equipment)
            thresholds = threshold_cache[equipment]
            result = detect_equipment(row, thresholds)
        cursor = connection.execute(
            """INSERT INTO sensor_data
            (timestamp,equipment_id,data_kind,temperature,pressure,vibration,threshold_set_id)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(equipment_id,timestamp,data_kind) DO NOTHING""",
            (row["timestamp"], row["equipment_id"], kind, row["temperature"],
             row["pressure"], row["vibration"], set_id if kind == "operation" else None))
        if cursor.rowcount == 0:
            continue
        saved_count += 1
        if kind == "baseline":
            continue
        for event in result["sensors"]:
            if event["severity"] == "정상":
                continue
            connection.execute(
                """INSERT INTO events
                (sensor_data_id,threshold_id,occurred_at,equipment_id,sensor_name,
                 measured_value,severity,direction,limit_value,deviation_value,
                 sigma_distance,reason)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(equipment_id,occurred_at,sensor_name) DO NOTHING""",
                (cursor.lastrowid, thresholds[event["sensor_name"]]["id"],
                 row["timestamp"], row["equipment_id"], event["sensor_name"],
                 event["measured_value"], event["severity"], event["direction"],
                 event["limit_value"], event["deviation_value"],
                 event["sigma_distance"], event["reason"]))
    return saved_count


def initialize_demo(connection, current_time=None):
    """최초 실행에서만 생성하며, 트랜잭션으로 부분 초기화를 방지합니다."""
    current_time = current_time or now_kst()
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT COUNT(*) FROM threshold_sets").fetchone()[0]:
            return False
        baseline_start = current_time - timedelta(days=14)
        baseline = generate_data(baseline_start, count=500, seed=42, data_kind="baseline")
        set_id = save_thresholds(connection, baseline, 42, {
            "profiles": PROFILES, "count_per_equipment": 500,
            "interval_minutes": 5, "seed": 42})
        save_measurements(connection, baseline)
        # 7일 분량이며 마지막 측정은 현재 시각입니다.
        count = 7 * 24 * 12
        operation = generate_data(current_time - timedelta(minutes=5 * (count - 1)),
                                  count=count, seed=43)
        save_measurements(connection, operation, set_id)
    return True


def append_demo(connection, seed=44, current_time=None):
    current_time = current_time or now_kst()
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        latest = connection.execute(
            "SELECT MAX(timestamp) FROM sensor_data WHERE data_kind='operation'").fetchone()[0]
        if latest is not None and str(current_time) <= latest:
            raise ValueError("같은 시각의 데이터는 추가할 수 없습니다. 잠시 후 다시 눌러 주세요.")
        set_id = connection.execute("SELECT MAX(id) FROM threshold_sets").fetchone()[0]
        frame = generate_data(current_time, count=1, seed=seed)
        return save_measurements(connection, frame, set_id)
