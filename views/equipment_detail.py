import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from config import EQUIPMENT_IDS, SENSORS, SENSOR_LABELS, UNITS
from queries import latest_measurements, sensor_history
from service import get_threshold_map
from detector import detect_equipment
from views.dashboard import BADGES


def build_sensor_chart(history, sensor):
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=history.timestamp, y=history.measured_value,
                               name="측정값", mode="lines+markers",
                               line={"color": "#2563eb", "width": 2}, marker={"size": 4}))
    limits = [("mean_value", "평균", "#64748b", "dot"),
              ("upper_2sigma", "2σ 상한", "#d97706", "dash"),
              ("upper_3sigma", "3σ 상한", "#dc2626", "dash")]
    if sensor != "vibration":
        limits += [("lower_2sigma", "2σ 하한", "#d97706", "dash"),
                   ("lower_3sigma", "3σ 하한", "#dc2626", "dash")]
    for column, label, color, dash in limits:
        figure.add_trace(go.Scatter(x=history.timestamp, y=history[column], name=label,
                                   mode="lines", line={"color": color, "dash": dash, "shape": "hv"}))
    figure.update_layout(height=340, margin={"l": 10, "r": 10, "t": 20, "b": 10},
                         xaxis_title="측정 시각 (KST)", yaxis_title=f"{SENSOR_LABELS[sensor]} ({UNITS[sensor]})",
                         legend={"orientation": "h", "y": 1.2}, hovermode="x unified")
    return figure


def render(connection):
    st.header("설비 상세")
    equipment = st.selectbox("설비 선택", EQUIPMENT_IDS)
    latest = latest_measurements(connection)
    selected = latest[latest.equipment_id == equipment]
    if selected.empty:
        st.info("선택한 설비의 측정 데이터가 없습니다.")
        return
    row = selected.iloc[0].to_dict()
    thresholds = get_threshold_map(connection, row["threshold_set_id"], equipment)
    result = detect_equipment(row, thresholds)
    st.subheader(f"{equipment} · {BADGES[result['status']]}")
    st.caption(f"최근 측정: {row['timestamp']} KST · 기준 버전 #{int(row['threshold_set_id'])}")
    for column, item in zip(st.columns(3), result["sensors"]):
        sensor = item["sensor_name"]
        column.metric(f"{SENSOR_LABELS[sensor]} · {item['severity']}",
                      f"{item['measured_value']:.3f} {UNITS[sensor]}")
    for reason in result["reasons"]:
        st.warning(reason)
    st.subheader("현재 적용 관리 기준")
    table = pd.DataFrame([{
        "센서": SENSOR_LABELS[sensor], "단위": UNITS[sensor], "표본 수": thresholds[sensor]["sample_count"],
        "평균": thresholds[sensor]["mean_value"], "표준편차": thresholds[sensor]["std_value"],
        "2σ 하한": thresholds[sensor]["lower_2sigma"], "2σ 상한": thresholds[sensor]["upper_2sigma"],
        "3σ 하한": thresholds[sensor]["lower_3sigma"], "3σ 상한": thresholds[sensor]["upper_3sigma"]
    } for sensor in SENSORS])
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption("정확히 2σ는 정상, 정확히 3σ는 주의입니다. 진동에는 하한을 적용하지 않습니다.")
    st.subheader("최근 100개 데이터")
    st.caption("각 측정값에 적용된 기준을 표시합니다. 기준 버전이 바뀌면 한계선도 바뀝니다.")
    for sensor in SENSORS:
        st.markdown(f"#### {SENSOR_LABELS[sensor]}")
        history = sensor_history(connection, equipment, sensor)
        st.plotly_chart(build_sensor_chart(history, sensor), use_container_width=True)
