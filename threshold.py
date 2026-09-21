"""기준 데이터만 사용해 설비별·센서별 표본 통계를 계산합니다."""
import json
import numpy as np
import pandas as pd
from config import EQUIPMENT_IDS, SENSORS, now_kst


def calculate_thresholds(baseline):
    required = {"equipment_id", "data_kind", *SENSORS}
    if not required.issubset(baseline.columns) or baseline.empty:
        raise ValueError("기준 산출에 필요한 데이터가 없습니다.")
    if not baseline.data_kind.eq("baseline").all():
        raise ValueError("판정 기준에는 기준 데이터만 사용할 수 있습니다.")
    if set(baseline.equipment_id) != set(EQUIPMENT_IDS):
        raise ValueError("설비 3대의 기준 데이터가 모두 필요합니다.")
    results = []
    for equipment, group in baseline.groupby("equipment_id"):
        for sensor in SENSORS:
            values = pd.to_numeric(group[sensor], errors="coerce")
            if len(values) < 2 or not np.isfinite(values).all():
                raise ValueError(f"{equipment} {sensor}: 유효한 표본이 2개 이상 필요합니다.")
            mean = float(values.mean())
            std = float(values.std(ddof=1))
            if not np.isfinite(mean) or not np.isfinite(std) or std <= 0:
                raise ValueError(f"{equipment} {sensor}: 표준편차가 0이거나 유효하지 않습니다.")
            results.append({
                "equipment_id": equipment, "sensor_name": sensor,
                "sample_count": len(values), "mean_value": mean, "std_value": std,
                "lower_2sigma": None if sensor == "vibration" else mean - 2 * std,
                "upper_2sigma": mean + 2 * std,
                "lower_3sigma": None if sensor == "vibration" else mean - 3 * std,
                "upper_3sigma": mean + 3 * std,
            })
    return results


def save_thresholds(connection, baseline, seed, generator_config):
    thresholds = calculate_thresholds(baseline)
    cursor = connection.execute(
        """INSERT INTO threshold_sets
        (created_at, random_seed, baseline_start, baseline_end, generator_config_json, std_ddof)
        VALUES (?, ?, ?, ?, ?, 1)""",
        (str(now_kst()), int(seed), str(baseline.timestamp.min()),
         str(baseline.timestamp.max()), json.dumps(generator_config, ensure_ascii=False)),
    )
    set_id = cursor.lastrowid
    for item in thresholds:
        connection.execute(
            """INSERT INTO thresholds
            (threshold_set_id,equipment_id,sensor_name,sample_count,mean_value,std_value,
             lower_2sigma,upper_2sigma,lower_3sigma,upper_3sigma)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (set_id, item["equipment_id"], item["sensor_name"], item["sample_count"],
             item["mean_value"], item["std_value"], item["lower_2sigma"],
             item["upper_2sigma"], item["lower_3sigma"], item["upper_3sigma"]),
        )
    return set_id
