# stock_app.py
import streamlit as st
import yfinance as yf
from yahooquery import search
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta

# ----------------------
# 종목명 → 티커 변환 함수
# ----------------------
def name_to_ticker(query: str):
    results = search(query)
    if "quotes" in results and len(results["quotes"]) > 0:
        return results["quotes"][0]["symbol"].upper()
    return None

# ----------------------
# 데이터 가져오기
# ----------------------
def get_price_and_eps(ticker: str):
    ticker = ticker.upper()
    stock = yf.Ticker(ticker)

    # 최근 5년 기간 설정
    end_date = datetime.today()
    start_date = end_date - timedelta(days=5*365)

    # 가격 데이터
    price = stock.history(start=start_date, end=end_date, interval="1d")["Close"]

    # 애널리스트 추정치 (forward EPS)
    eps = stock.analysis
    if eps is not None and not eps.empty:
        eps.index = pd.to_datetime(eps.index)
        forward_eps = eps["Earnings Estimate Average"].dropna()
    else:
        forward_eps = None

    return price, forward_eps

# ----------------------
# Streamlit UI
# ----------------------
st.set_page_config(page_title="Stock Search", page_icon="📈", layout="centered")

# 검색창 스타일 (구글 메인페이지 느낌)
st.markdown(
    """
    <style>
    .centered-title {text-align: center; font-size: 2.2em; margin-bottom: 30px;}
    .stTextInput > div > div > input {
        text-align: center;
        font-size: 1.2em;
        height: 3em;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("<h1 class='centered-title'>📈 Stock Search</h1>", unsafe_allow_html=True)

query = st.text_input("Search stock by name (한글/영문 가능)", "")

if query:
    ticker = name_to_ticker(query)
    if ticker:
        st.write(f"**검색 결과 → 티커: {ticker}**")

        price, forward_eps = get_price_and_eps(ticker)

        if price is not None and not price.empty:
            fig, ax1 = plt.subplots(figsize=(10, 5))

            ax1.plot(price.index, price.values, color="blue", label="Price (USD)")
            ax1.set_ylabel("Price (USD)", color="blue")
            ax1.tick_params(axis="y", labelcolor="blue")

            if forward_eps is not None and not forward_eps.empty:
                ax2 = ax1.twinx()
                ax2.plot(forward_eps.index, forward_eps.values, color="red", label="Forward EPS")
                ax2.set_ylabel("Forward EPS", color="red")
                ax2.tick_params(axis="y", labelcolor="red")

            plt.title(f"{ticker} - Price & 12M Forward EPS (Last 5 Years)")
            st.pyplot(fig)
        else:
            st.warning("가격 데이터를 불러올 수 없습니다.")
    else:
        st.error("해당 이름으로 종목을 찾을 수 없습니다.")
