# app.py (Streamlit)
import streamlit as st
import yfinance as yf
from yahooquery import search
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
import traceback

st.set_page_config(page_title="Stock Search", page_icon="📈", layout="centered")

# 캐시: 동일 쿼리에 대해 API 호출 줄임
@st.cache_data(ttl=3600)
def name_to_ticker(query: str):
    """한글/영문 입력을 받아 관련 티커(가장 유력한 1개)를 반환."""
    q = query.strip()
    if q == "":
        return None
    # 먼저, 입력이 이미 티커 형태일 수 있으므로 대문자로 변환 시도
    if len(q) <= 5 and q.isalnum():
        return q.upper()
    try:
        res = search(q)
        # yahooquery.search 반환 형식은 dict이며 'quotes' 키에 후보가 들어감
        if isinstance(res, dict) and 'quotes' in res and len(res['quotes']) > 0:
            return res['quotes'][0]['symbol'].upper()
    except Exception:
        # 검색 실패 시 None 반환 (상세 에러는 로그로)
        return None
    return None

@st.cache_data(ttl=600)
def get_price_and_forward_eps(ticker: str, months_interval: int = 60):
    """
    ticker -> (price_df(monthly), forward_eps_value_or_None)
    months_interval: 최근 몇 개월(기본 60개월 = 약 5년)
    """
    ticker = ticker.upper()
    end = datetime.today()
    start = end - timedelta(days=365*5)  # 기본 5년
    try:
        t = yf.Ticker(ticker)

        # --- 가격 (월별 종가, auto_adjust=True 권장)
        df_price = t.history(start=start.strftime("%Y-%m-%d"),
                             end=end.strftime("%Y-%m-%d"),
                             interval="1mo",
                             auto_adjust=True)
        if df_price is None or df_price.empty:
            # 데이터가 없으면 전체 기간으로 fallback
            df_price = t.history(period="max", interval="1mo", auto_adjust=True)

        # 표준화
        if 'Close' in df_price.columns:
            df_price = df_price[['Close']].rename(columns={'Close': 'Price'})
        elif 'Adj Close' in df_price.columns:
            df_price = df_price[['Adj Close']].rename(columns={'Adj Close': 'Price'})
        else:
            # 어떤 경우에도 Price 칼럼 생성
            df_price['Price'] = df_price.iloc[:, 0]

        # 인덱스 월말로 정렬
        try:
            df_price.index = pd.to_datetime(df_price.index).to_period('M').to_timestamp('M')
        except Exception:
            pass

        # --- forward EPS 시도 1: yfinance.info
        forward_eps = None
        try:
            info = t.info  # 이 호출이 실패할 수 있음 (rate limit 등)
            if isinstance(info, dict):
                forward_eps = info.get('forwardEps', None)
        except Exception:
            forward_eps = None

        # --- forward EPS 시도 2: yahooquery summary_detail (폴백)
        if forward_eps is None:
            try:
                from yahooquery import Ticker as YQTicker
                yq = YQTicker(ticker)
                sd = yq.summary_detail
                # summary_detail은 dict 또는 DataFrame일 수 있음
                if isinstance(sd, dict):
                    d = sd.get(ticker, {})
                    forward_eps = d.get('forwardEps', None)
                elif hasattr(sd, 'get'):
                    forward_eps = sd.get(ticker, {}).get('forwardEps', None)
            except Exception:
                forward_eps = None

        return df_price, forward_eps
    except Exception as e:
        # 예외 발생 시 None 반환 (호출부에서 처리)
        raise RuntimeError(f"데이터 로드 중 예외: {e}\n{traceback.format_exc()}")

# UI (구글 스타일 심플 검색창)
st.markdown(
    """
    <style>
    .centered-title {text-align: center; font-size: 2.2em; margin-bottom: 18px;}
    .stTextInput > div > div > input {
        text-align: center;
        font-size: 1.1em;
        height: 3em;
    }
    .stButton>button { width: 100px; height: 2.5em; }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("<h1 class='centered-title'>📈 Stock Search</h1>", unsafe_allow_html=True)
query = st.text_input("Search stock by name (한글/영문 가능)")

if st.button("검색") or (query and not st.session_state.get("searched")):
    # 버튼 또는 Enter 일 때 실행
    st.session_state["searched"] = True
    if not query:
        st.info("종목명(한글/영문) 또는 티커를 입력해 주세요.")
    else:
        ticker = name_to_ticker(query)
        if not ticker:
            st.error("해당 이름으로 종목을 찾을 수 없습니다. (검색 API 응답 없음 또는 오타)")
        else:
            st.success(f"검색 결과 → 티커: **{ticker}**")
            try:
                price_df, forward_eps = get_price_and_forward_eps(ticker)
            except Exception as e:
                st.error("데이터를 불러오는 중 에러가 발생했습니다. 앱 로그를 확인하세요.")
                st.code(str(e))
                price_df = pd.DataFrame()
                forward_eps = None

            if price_df is None or price_df.empty:
                st.warning("가격 데이터를 불러올 수 없습니다.")
            else:
                # 그래프 준비 (Price: 왼쪽, Forward EPS: 오른쪽)
                fig, ax1 = plt.subplots(figsize=(11,5))
                ax1.plot(price_df.index, price_df['Price'], label='Price', linewidth=2, marker=None)
                ax1.set_xlabel("Date")
                ax1.set_ylabel("Price (USD)")
                ax1.grid(True, linestyle='--', linewidth=0.5, alpha=0.6)
                ax1.tick_params(axis="y")

                if forward_eps is not None:
                    # EPS를 월별 시계열(상수)로 만들어 오른쪽 축에 그림
                    eps_series = pd.Series(forward_eps, index=price_df.index)
                    ax2 = ax1.twinx()
                    ax2.plot(eps_series.index, eps_series.values, color='tab:orange', label='12-month forward EPS', linewidth=2)
                    ax2.set_ylabel("Forward EPS (USD)")
                    ax2.tick_params(axis="y", labelcolor="tab:orange")

                    # 범례 합치기
                    lines1, labels1 = ax1.get_legend_handles_labels()
                    lines2, labels2 = ax2.get_legend_handles_labels()
                    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
                else:
                    ax1.legend(loc='upper left')
                    st.info("Forward EPS 데이터가 제공되지 않습니다 (없거나 API에서 가져오지 못함).")

                plt.title(f"{ticker} - Price vs 12-month forward EPS (Last ~5 years)")
                st.pyplot(fig)

                # 선택적으로 상세 정보 출력
                with st.expander("데이터 샘플 보기"):
                    st.write("Price (recent rows):")
                    st.dataframe(price_df.tail(10))

                # 디버그용: forward_eps 값 노출
                st.write("Forward EPS:", forward_eps)
