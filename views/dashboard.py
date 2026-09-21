import streamlit as st
from config import EQUIPMENT_IDS, SENSORS, SENSOR_LABELS, UNITS, now_kst
from detector import detect_equipment
from service import get_threshold_map
from queries import latest_measurements, event_summary, recent_abnormal_events

BADGES = {"정상": "🟢 정상", "주의": "🟠 주의", "이상": "🔴 이상"}


def render(connection):
    st.header("설비 현황")
    st.caption("최신 측정값 기준 · 한국 시간(KST) · 색상과 문자를 함께 표시합니다.")
    latest = latest_measurements(connection)
    equipment_results = {}
    for row in latest.to_dict("records"):
        thresholds = get_threshold_map(connection, row["threshold_set_id"], row["equipment_id"])
        equipment_results[row["equipment_id"]] = (row, detect_equipment(row, thresholds))
    counts = {state: sum(result["status"] == state for _, result in equipment_results.values())
              for state in BADGES}
    summary = event_summary(connection, now_kst().date())
    labels = [("전체 설비", len(EQUIPMENT_IDS)), ("정상", counts["정상"]),
              ("주의", counts["주의"]), ("이상", counts["이상"]),
              ("오늘 이상 이벤트", summary["today_abnormal"]), ("미조치 이벤트", summary["unresolved"])]
    for column, (label, value) in zip(st.columns(6), labels):
        column.metric(label, value)
    st.caption("이벤트는 센서별 측정 건수입니다. 미조치는 주의·이상 중 '조치 완료'가 아닌 건수입니다.")
    for column, equipment in zip(st.columns(3), EQUIPMENT_IDS):
        with column:
            with st.container(border=True):
                st.subheader(equipment)
                if equipment not in equipment_results:
                    st.info("데이터 없음")
                    continue
                row, result = equipment_results[equipment]
                st.markdown(f"### {BADGES[result['status']]}")
                st.caption(f"측정 시각: {row['timestamp']}")
                for sensor in SENSORS:
                    st.write(f"{SENSOR_LABELS[sensor]}  **{row[sensor]:.2f} {UNITS[sensor]}**")
                for reason in result["reasons"]:
                    st.caption(reason)
    st.subheader("최근 이상 알림 10건")
    events = recent_abnormal_events(connection)
    if events.empty:
        st.info("아직 이상 이벤트가 없습니다.")
    else:
        st.dataframe(events, hide_index=True, use_container_width=True)
