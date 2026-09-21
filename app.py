"""실행: python -m streamlit run app.py"""
import logging
import sqlite3
import streamlit as st
from config import NOTICE
from database import connect_database
from service import initialize_demo, append_demo
from views import dashboard, equipment_detail

logger = logging.getLogger(__name__)


def main():
    st.set_page_config(page_title="SEMI-GUARD", page_icon="🛡️", layout="wide")
    st.title("SEMI-GUARD")
    st.caption("설비 데이터 기반 이상 판정 및 점검 기록 시스템")
    st.info(NOTICE)
    st.sidebar.title("SEMI-GUARD")
    st.sidebar.caption("가상 설비 3대 · 통계 기반 모니터링")
    page = st.sidebar.radio("화면", ["종합 대시보드", "설비 상세"])
    seed = st.sidebar.number_input("추가 데이터 시드", min_value=0, max_value=2147483647, value=44, step=1)
    add_data = st.sidebar.button("현재 시각 가상 데이터 추가")
    st.sidebar.caption("새로고침은 데이터를 추가하지 않습니다. 버튼을 누르면 설비별 1개씩 추가합니다.")
    connection = None
    try:
        connection = connect_database()
        initialize_demo(connection)
        if add_data:
            count = append_demo(connection, seed=int(seed))
            st.sidebar.success(f"가상 측정값 {count}개를 저장했습니다.")
        if page == "종합 대시보드":
            dashboard.render(connection)
        else:
            equipment_detail.render(connection)
    except (ValueError, sqlite3.Error, OSError) as error:
        logger.exception("SEMI-GUARD 처리 실패")
        if isinstance(error, ValueError):
            st.error(str(error))
        else:
            st.error("데이터 저장소를 열거나 저장하지 못했습니다. 폴더의 쓰기 권한을 확인하고 잠시 후 다시 시도해 주세요.")
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
