"""점검 이력은 추가 저장하고 이벤트의 현재 진행 상태를 함께 갱신합니다."""
import json
from checklist import CHECKLISTS
from config import PROGRESS_STATES, now_kst


def latest_inspection(connection, event_id):
    return connection.execute(
        "SELECT * FROM inspection_records WHERE event_id=? ORDER BY id DESC LIMIT 1",
        (int(event_id),)).fetchone()


def save_inspection(connection, event_id, checked, suspected_cause, action_taken,
                    progress_status, expected_record_id=None):
    if progress_status not in PROGRESS_STATES:
        raise ValueError("올바른 진행 상태를 선택하세요.")
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        event = connection.execute("SELECT * FROM events WHERE id=?", (int(event_id),)).fetchone()
        if event is None:
            raise ValueError("선택한 이벤트를 찾을 수 없습니다.")
        previous = latest_inspection(connection, event_id)
        actual_record_id = previous["id"] if previous else None
        if expected_record_id != actual_record_id:
            raise ValueError("다른 창에서 기록이 변경됐습니다. 화면을 새로고침한 뒤 다시 확인하세요.")
        items = CHECKLISTS[event["sensor_name"]]
        if set(checked) != set(items) or any(type(value) is not bool for value in checked.values()):
            raise ValueError("해당 센서의 모든 점검 항목을 확인하세요.")
        suspected_cause = suspected_cause.strip()
        action_taken = action_taken.strip()
        if progress_status == "조치 완료":
            if not all(checked.values()):
                raise ValueError("조치 완료로 저장하려면 모든 점검 항목을 완료하세요.")
            if not suspected_cause or not action_taken:
                raise ValueError("추정 원인과 조치 내용을 모두 입력하세요. 원인이 불명확하면 원인 미확정으로 기록할 수 있습니다.")
        cursor = connection.execute(
            """INSERT INTO inspection_records
            (event_id,recorded_at,checklist_json,suspected_cause,action_taken,progress_status)
            VALUES (?,?,?,?,?,?)""",
            (int(event_id), str(now_kst()), json.dumps(checked, ensure_ascii=False),
             suspected_cause, action_taken, progress_status))
        connection.execute("UPDATE events SET progress_status=? WHERE id=?",
                           (progress_status, int(event_id)))
        return cursor.lastrowid
