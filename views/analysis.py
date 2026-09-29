"""SQL 집계 결과를 보여 주는 분석 화면."""
from datetime import date, timedelta
import plotly.graph_objects as go
import streamlit as st
from analytics import daily_anomalies, equipment_sensor_anomalies, frequent_anomaly_types
from config import EQUIPMENT_IDS, SENSORS, SENSOR_LABELS, now_kst


def render(connection):
    st.header("분석")
    st.caption("가상 데이터 · 심각도가 '이상'인 센서 이벤트만 집계합니다. 주의는 제외합니다.")
    st.caption("한 측정 시각에 센서 2개가 이상이면 2건입니다. KST 기준으로 시작일과 종료일을 모두 포함합니다.")
    today = now_kst().date()
    left, right = st.columns(2)
    start = left.date_input("분석 시작일", today - timedelta(days=6),
                            min_value=date(2000, 1, 1), max_value=today)
    end = right.date_input("분석 종료일", today, min_value=date(2000, 1, 1), max_value=today)
    st.caption("조회 기간은 최대 366일입니다.")
    try:
        daily = daily_anomalies(connection, start, end)
        heatmap = equipment_sensor_anomalies(connection, start, end)
        types = frequent_anomaly_types(connection, start, end)
    except ValueError as error:
        st.error(str(error))
        return

    st.subheader("날짜별 이상 추이")
    figure = go.Figure(go.Scatter(x=daily.day, y=daily.event_count, mode="lines+markers",
                                  name="이상 건수", line={"color": "#dc2626"}))
    figure.update_layout(xaxis_title="발생 날짜 (KST)", yaxis_title="센서 이벤트 수 (건)",
                         yaxis={"rangemode": "tozero", "dtick": 1 if daily.event_count.max() < 10 else None})
    st.plotly_chart(figure, use_container_width=True)

    st.subheader("설비별 × 센서별 이상 발생")
    # pivot은 SQL 집계 결과의 배치만 바꿉니다. 재집계하지 않습니다.
    matrix = heatmap.pivot(index="equipment_id", columns="sensor_name", values="event_count")
    matrix = matrix.reindex(index=EQUIPMENT_IDS, columns=SENSORS)
    figure = go.Figure(go.Heatmap(z=matrix.values, x=[SENSOR_LABELS[s] for s in SENSORS],
                                  y=list(EQUIPMENT_IDS), colorscale="Reds", zmin=0,
                                  zmax=max(1, int(matrix.to_numpy().max())),
                                  text=matrix.values, texttemplate="%{text}건",
                                  hovertemplate="설비: %{y}<br>센서: %{x}<br>이상: %{z}건<extra></extra>",
                                  colorbar={"title": "건수"}))
    figure.update_layout(xaxis_title="센서", yaxis_title="설비")
    st.plotly_chart(figure, use_container_width=True)

    st.subheader("자주 발생한 이상 유형")
    if types.empty:
        st.info("선택한 기간에 이상 이벤트가 없습니다. 모든 집계는 0건입니다.")
    else:
        types["sensor_name"] = types.sensor_name.map(SENSOR_LABELS)
        st.dataframe(types.rename(columns={"sensor_name": "센서", "direction": "이상 유형",
                                           "event_count": "발생 건수"}),
                     hide_index=True, use_container_width=True)
