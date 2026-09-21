"""정확히 2σ는 정상, 정확히 3σ는 주의. 진동에는 상한만 적용합니다."""
import math
from config import SENSORS, SENSOR_LABELS, UNITS, STATUS_RANK


def detect_sensor(sensor, value, threshold):
    if sensor not in SENSORS:
        raise ValueError("지원하지 않는 센서입니다.")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("측정값은 결측이나 무한값이 아닌 숫자여야 합니다.")
    mean, std = threshold["mean_value"], threshold["std_value"]
    if not math.isfinite(std) or std <= 0:
        raise ValueError("유효한 표준편차가 필요합니다.")
    direction = None
    severity = "정상"
    limit = None
    # 저장된 경계와 직접 비교하여 정확한 경계 포함 규칙을 유지합니다.
    for sigma, candidate in [(3, "이상"), (2, "주의")]:
        upper = threshold[f"upper_{sigma}sigma"]
        lower = threshold[f"lower_{sigma}sigma"]
        if value > upper:
            severity, direction, limit = candidate, "상한 초과", upper
            break
        if sensor != "vibration" and lower is not None and value < lower:
            severity, direction, limit = candidate, "하한 미달", lower
            break
    deviation = 0.0 if limit is None else abs(value - limit)
    reason = "관리한계 이내입니다."
    if limit is not None:
        sigma_label = "3σ" if severity == "이상" else "2σ"
        side = "상한" if direction == "상한 초과" else "하한"
        verb = "초과" if direction == "상한 초과" else "미달"
        reason = (f"{SENSOR_LABELS[sensor]} {severity}: {value:.3f}{UNITS[sensor]}, "
                  f"{sigma_label} {side} {limit:.3f}{UNITS[sensor]}보다 "
                  f"{deviation:.3f}{UNITS[sensor]} {verb}")
    return {"sensor_name": sensor, "measured_value": value, "severity": severity,
            "direction": direction, "limit_value": limit, "deviation_value": deviation,
            "sigma_distance": abs(value - mean) / std, "reason": reason}


def detect_equipment(measurement, thresholds):
    details = [detect_sensor(sensor, measurement[sensor], thresholds[sensor])
               for sensor in SENSORS]
    overall = max((item["severity"] for item in details), key=STATUS_RANK.get)
    return {"status": overall, "sensors": details,
            "reasons": [item["reason"] for item in details if item["severity"] != "정상"]}
