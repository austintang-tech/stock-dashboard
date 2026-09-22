import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from common import CATEGORICAL_COLORS, sidebar_tickers, sidebar_period, load_all_history, fetch_dividends

st.set_page_config(page_title="ETF / 股票追蹤儀表板", page_icon="📈", layout="wide")

st.title("📈 ETF / 股票追蹤儀表板")

tickers = sidebar_tickers()
start_date, end_date = sidebar_period()

if not tickers:
    st.info("請在左側輸入至少一個標的代碼。")
    st.stop()

data = load_all_history(tickers, start_date, end_date)
if not data:
    st.stop()

# --- 現價與漲跌 ---
st.subheader("現價快照")
cols = st.columns(len(data))
for col, (t, hist) in zip(cols, data.items()):
    last_close = hist["Close"].iloc[-1]
    prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else last_close
    change_pct = (last_close / prev_close - 1) * 100 if prev_close else 0
    col.metric(t, f"{last_close:,.2f}", delta=f"{change_pct:+.2f}%")

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
