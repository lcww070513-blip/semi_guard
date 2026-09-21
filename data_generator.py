"""같은 시드·시작 시각·개수·간격이면 같은 데이터가 생성됩니다."""
import numpy as np
import pandas as pd
from config import EQUIPMENT_IDS, SENSORS

# 설비별 가상 정상 분포의 (평균, 표준편차)
PROFILES = {
    "EQ-01": {"temperature": (70, 2), "pressure": (100, 3), "vibration": (2, 0.2)},
    "EQ-02": {"temperature": (72, 2.5), "pressure": (105, 3.5), "vibration": (2.2, 0.25)},
    "EQ-03": {"temperature": (68, 1.8), "pressure": (98, 2.8), "vibration": (1.8, 0.18)},
}


def generate_data(start, count=500, interval_minutes=5, seed=42,
                  data_kind="operation", warning_probability=0.06,
                  abnormal_probability=0.03):
    if count < 1 or interval_minutes < 1:
        raise ValueError("데이터 개수와 측정 간격은 1 이상이어야 합니다.")
    if data_kind not in ("baseline", "operation"):
        raise ValueError("데이터 종류는 baseline 또는 operation이어야 합니다.")
    probabilities = [warning_probability, abnormal_probability]
    if not all(np.isfinite(p) and 0 <= p <= 1 for p in probabilities) or sum(probabilities) > 1:
        raise ValueError("주의·이상 확률은 각각 0~1이고 합은 1 이하여야 합니다.")
    start = pd.Timestamp(start)
    if pd.isna(start) or start.tzinfo is not None:
        raise ValueError("시작 시각은 시간대 표시가 없는 한국 시간으로 입력하세요.")
    rng = np.random.default_rng(seed)
    times = pd.date_range(start, periods=count, freq=f"{interval_minutes}min")
    frames = []
    for equipment in EQUIPMENT_IDS:
        frame = pd.DataFrame({"timestamp": times.strftime("%Y-%m-%d %H:%M:%S"),
                              "equipment_id": equipment, "data_kind": data_kind})
        for sensor in SENSORS:
            mean, std = PROFILES[equipment][sensor]
            distances = rng.normal(0, 1, count)
            if data_kind == "operation":
                choice = rng.random(count)
                warning = choice < warning_probability
                abnormal = (choice >= warning_probability) & (choice < sum(probabilities))
                signs = np.ones(count) if sensor == "vibration" else rng.choice([-1, 1], count)
                distances[warning] = signs[warning] * rng.uniform(2.2, 2.9, warning.sum())
                distances[abnormal] = signs[abnormal] * rng.uniform(3.3, 5.0, abnormal.sum())
            frame[sensor] = mean + std * distances
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values(
        ["timestamp", "equipment_id"]).reset_index(drop=True)
