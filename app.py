import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import date, timedelta

st.set_page_config(page_title="ETF / 股票追蹤儀表板", page_icon="📈", layout="wide")

DEFAULT_TICKERS = ["0050.TW", "0052.TW"]
CATEGORICAL_COLORS = ["#3B82F6", "#F59E0B", "#10B981", "#8B5CF6", "#EF4444", "#06B6D4"]

PERIOD_OPTIONS = {
    "近3個月": 90,
    "近6個月": 180,
    "近1年": 365,
    "近3年": 365 * 3,
    "近5年": 365 * 5,
}


@st.cache_data(ttl=3600)
def fetch_history(ticker: str, start: date, end: date) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    if df.empty:
        return df
    df.index = df.index.tz_localize(None)
    return df


@st.cache_data(ttl=3600)
def fetch_dividends(ticker: str) -> pd.Series:
    div = yf.Ticker(ticker).dividends
    if len(div):
        div.index = div.index.tz_localize(None)
    return div


@st.cache_data(ttl=3600)
def fetch_info(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).fast_info
    except Exception:
        return {}


def stat_tile(col, label, value, delta=None, delta_color="normal"):
    col.metric(label, value, delta=delta, delta_color=delta_color)


st.title("📈 ETF / 股票追蹤儀表板")

with st.sidebar:
    st.header("設定")
    tickers_input = st.text_area(
        "追蹤標的（每行一個，台股請加 .TW，例如 0050.TW）",
        value="\n".join(DEFAULT_TICKERS),
        height=100,
    )
    tickers = [t.strip().upper() for t in tickers_input.splitlines() if t.strip()]

    period_label = st.selectbox("時間範圍", list(PERIOD_OPTIONS.keys()), index=2)
    days = PERIOD_OPTIONS[period_label]
    start_date = date.today() - timedelta(days=days)
    end_date = date.today() + timedelta(days=1)

    st.caption("資料每小時自動更新一次（快取），來源：Yahoo Finance。")
    if st.button("立即重新抓取資料"):
        st.cache_data.clear()

if not tickers:
    st.info("請在左側輸入至少一個標的代碼。")
    st.stop()

data = {}
for t in tickers:
    hist = fetch_history(t, start_date, end_date)
    if hist.empty:
        st.warning(f"抓不到「{t}」的資料，請確認代碼是否正確（台股例如 0050.TW）。")
        continue
    data[t] = hist

if not data:
    st.stop()

# --- 現價與漲跌 ---
st.subheader("現價快照")
cols = st.columns(len(data))
for col, (t, hist) in zip(cols, data.items()):
    last_close = hist["Close"].iloc[-1]
    prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else last_close
    change_pct = (last_close / prev_close - 1) * 100 if prev_close else 0
    stat_tile(col, t, f"{last_close:,.2f}", delta=f"{change_pct:+.2f}%")

# --- 走勢比較（指數化到100，避免不同價位無法比較） ---
st.subheader("走勢比較（以區間起點指數化為 100）")
fig = go.Figure()
for i, (t, hist) in enumerate(data.items()):
    indexed = hist["Close"] / hist["Close"].iloc[0] * 100
    fig.add_trace(
        go.Scatter(
            x=indexed.index,
            y=indexed.values,
            mode="lines",
            name=t,
            line=dict(color=CATEGORICAL_COLORS[i % len(CATEGORICAL_COLORS)], width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.1f}<extra>" + t + "</extra>",
        )
    )
fig.update_layout(
    height=450,
    hovermode="x unified",
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    yaxis_title="指數化價格（起點=100）",
)
st.plotly_chart(fig, width="stretch")

# --- 區間報酬 ---
st.subheader("區間報酬")
rows = []
for t, hist in data.items():
    total_return = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
    div = fetch_dividends(t)
    div_in_range = div[(div.index >= pd.Timestamp(start_date)) & (div.index <= pd.Timestamp(end_date))]
    div_sum = div_in_range.sum()
    div_yield_on_start = (div_sum / hist["Close"].iloc[0]) * 100 if len(hist) else 0
    rows.append(
        {
            "標的": t,
            "價格報酬 %": round(total_return, 2),
            "區間配息合計": round(div_sum, 2),
            "配息報酬 %": round(div_yield_on_start, 2),
            "總報酬 % (價格+配息)": round(total_return + div_yield_on_start, 2),
        }
    )
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

# --- 配息紀錄 ---
st.subheader("配息紀錄")
tabs = st.tabs(list(data.keys()))
for tab, t in zip(tabs, data.keys()):
    with tab:
        div = fetch_dividends(t)
        div_in_range = div[(div.index >= pd.Timestamp(start_date)) & (div.index <= pd.Timestamp(end_date))]
        if div_in_range.empty:
            st.caption("這段時間內沒有配息紀錄。")
        else:
            df_div = div_in_range.sort_index(ascending=False).rename("配息金額").reset_index()
            df_div.columns = ["除息日", "配息金額"]
            st.dataframe(df_div, width="stretch", hide_index=True)

st.caption("資料來源：Yahoo Finance（yfinance）。僅供個人參考，非投資建議。")
