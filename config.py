"""학습용 설정. 실제 기업의 공정 조건이나 관리 기준이 아닙니다."""
from datetime import datetime, timedelta, timezone

EQUIPMENT_IDS = ("EQ-01", "EQ-02", "EQ-03")
SENSORS = ("temperature", "pressure", "vibration")
SENSOR_LABELS = {"temperature": "온도", "pressure": "압력", "vibration": "진동"}
UNITS = {"temperature": "°C", "pressure": "kPa", "vibration": "mm/s"}
STATUS_RANK = {"정상": 0, "주의": 1, "이상": 2}
PROGRESS_STATES = ("미확인", "점검 중", "조치 완료")
KST = timezone(timedelta(hours=9))
NOTICE = "학습용 가상 데이터입니다. 실제 기업 데이터·내부 기준을 사용하지 않으며 실제 설비 운전·안전 판단용이 아닙니다."


def now_kst():
    return datetime.now(KST).replace(tzinfo=None, microsecond=0)
