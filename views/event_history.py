import json
from datetime import date
import streamlit as st
from config import EQUIPMENT_IDS, SENSORS, SENSOR_LABELS, PROGRESS_STATES, now_kst
from checklist import CHECKLISTS
from inspection import latest_inspection, save_inspection
from queries import event_date_bounds, filtered_events
from database import query_frame


def render(connection):
    st.header("이상 이력 및 조치")
    st.caption("주의·이상 이벤트를 점검합니다. 지속된 이상은 측정 시각별 별도 이벤트입니다.")
    if "inspection_notice" in st.session_state:
        st.success(st.session_state.pop("inspection_notice"))
    bounds = event_date_bounds(connection)
    if bounds[0] is None:
        st.info("점검할 이벤트가 없습니다.")
        return
    columns = st.columns(2)
    start = columns[0].date_input("시작 날짜", date.fromisoformat(bounds[0]), key="history_start")
    end = columns[1].date_input("종료 날짜", max(now_kst().date(), date.fromisoformat(bounds[1])), key="history_end")
    columns = st.columns(4)
    equipment = columns[0].selectbox("설비", ("전체", *EQUIPMENT_IDS), key="history_equipment")
    sensor = columns[1].selectbox("센서", ("전체", *SENSORS),
                                 format_func=lambda value: SENSOR_LABELS.get(value, value))
    severity = columns[2].selectbox("심각도", ("전체", "주의", "이상"))
    progress = columns[3].selectbox("진행 상태 필터", ("전체", *PROGRESS_STATES))
    if start > end:
        st.warning("시작 날짜는 종료 날짜보다 늦을 수 없습니다.")
        return
    filters = (str(start), str(end), equipment, sensor, severity, progress)
    if st.session_state.get("history_filters") != filters:
        st.session_state["history_page"] = 1
        st.session_state["history_filters"] = filters
    page = int(st.number_input("페이지", min_value=1, step=1, key="history_page"))
    events, total = filtered_events(connection, start, end, equipment, sensor, severity, progress, page)
    st.caption(f"총 {total:,}건 · 페이지당 100건 · 최대 {max(1, (total + 99) // 100)}페이지")
    if events.empty:
        st.info("조건에 맞는 이벤트가 없습니다. 페이지와 필터를 확인하세요.")
        return
    display = events[["id", "occurred_at", "equipment_id", "sensor_name", "measured_value",
                      "deviation_value", "severity", "progress_status"]].copy()
    display["sensor_name"] = display.sensor_name.map(SENSOR_LABELS)
    display.columns = ["번호", "발생 시각", "설비", "센서", "측정값", "이탈량", "심각도", "진행 상태"]
    st.dataframe(display, hide_index=True, use_container_width=True)
    options = events.id.tolist()
    labels = {int(row["id"]): f"#{row['id']} · {row['equipment_id']} · {SENSOR_LABELS[row['sensor_name']]} · {row['occurred_at']}"
              for row in events.to_dict("records")}
    event_id = st.selectbox("점검할 이벤트", options, format_func=lambda value: labels[value])
    event = events[events.id == event_id].iloc[0]
    st.warning(event.reason)
    previous = latest_inspection(connection, event_id)
    previous_id = previous["id"] if previous else None
    checked_before = json.loads(previous["checklist_json"]) if previous else {}
    form_key = f"inspection_{event_id}_{previous_id}"
    with st.form(form_key):
        st.subheader("점검 체크리스트")
        checked = {item: st.checkbox(item, value=checked_before.get(item, False),
                                    key=f"{form_key}_{index}")
                   for index, item in enumerate(CHECKLISTS[event.sensor_name])}
        cause = st.text_area("추정 원인", value=previous["suspected_cause"] if previous else "",
                             placeholder="예: 냉각 상태 확인 필요 / 원인 미확정", key=f"{form_key}_cause")
        action = st.text_area("조치 내용", value=previous["action_taken"] if previous else "",
                              placeholder="확인·조치한 내용과 재측정 결과를 기록하세요.", key=f"{form_key}_action")
        state = st.selectbox("저장할 진행 상태", PROGRESS_STATES,
                             index=PROGRESS_STATES.index(event.progress_status), key=f"{form_key}_state")
        submitted = st.form_submit_button("점검 기록 저장", type="primary")
    if submitted:
        try:
            save_inspection(connection, event_id, checked, cause, action, state, previous_id)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state["inspection_notice"] = "점검 기록과 진행 상태를 저장했습니다."
            st.rerun()
    st.subheader("이 이벤트의 점검 기록")
    records = query_frame(connection, """
        SELECT recorded_at AS 기록시각, progress_status AS 진행상태,
               suspected_cause AS 추정원인, action_taken AS 조치내용,
               checklist_json AS 점검항목
        FROM inspection_records WHERE event_id=? ORDER BY id DESC
    """, (int(event_id),))
    if records.empty:
        st.caption("아직 저장된 점검 기록이 없습니다.")
    else:
        st.dataframe(records, hide_index=True, use_container_width=True)
