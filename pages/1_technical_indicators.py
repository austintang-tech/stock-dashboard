import streamlit as st
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from common import CATEGORICAL_COLORS, sidebar_tickers, sidebar_period, load_all_history

st.set_page_config(page_title="技術指標面板", page_icon="📊", layout="wide")
st.title("📊 技術指標面板")
st.caption("以下為客觀計算出的技術指標數值，僅供參考，不構成任何買賣建議。")

tickers = sidebar_tickers()
start_date, end_date = sidebar_period()

if not tickers:
    st.info("請在左側輸入至少一個標的代碼。")
    st.stop()

data = load_all_history(tickers, start_date, end_date)
if not data:
    st.stop()


def compute_indicators(close: pd.Series) -> pd.DataFrame:
    out = pd.DataFrame(index=close.index)
    out["close"] = close
    out["ma20"] = close.rolling(20).mean()
    out["ma60"] = close.rolling(60).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    out["rsi"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    return out


def ma_cross_status(ind: pd.DataFrame) -> str:
    diff = ind["ma20"] - ind["ma60"]
    diff = diff.dropna()
    if len(diff) < 2:
        return "資料不足"
    recent = diff.iloc[-5:]
    sign_changes = (recent > 0).astype(int).diff().dropna()
    if (sign_changes == 1).any():
        return "🟢 近5日內出現黃金交叉（MA20 上穿 MA60）"
    if (sign_changes == -1).any():
        return "🔴 近5日內出現死亡交叉（MA20 下穿 MA60）"
    return "多頭排列（MA20 > MA60）" if diff.iloc[-1] > 0 else "空頭排列（MA20 < MA60）"


def rsi_status(ind: pd.DataFrame) -> str:
    val = ind["rsi"].dropna()
    if val.empty:
        return "資料不足"
    v = val.iloc[-1]
    if v >= 70:
        return f"🔴 超買區（RSI = {v:.1f}）"
    if v <= 30:
        return f"🟢 超賣區（RSI = {v:.1f}）"
    return f"中性（RSI = {v:.1f}）"


def macd_status(ind: pd.DataFrame) -> str:
    hist = ind["macd_hist"].dropna()
    if len(hist) < 2:
        return "資料不足"
    recent = hist.iloc[-5:]
    sign_changes = (recent > 0).astype(int).diff().dropna()
    if (sign_changes == 1).any():
        return "🟢 近5日內 MACD 上穿訊號線"
    if (sign_changes == -1).any():
        return "🔴 近5日內 MACD 下穿訊號線"
    return "MACD 在訊號線上方" if hist.iloc[-1] > 0 else "MACD 在訊號線下方"


for t, hist in data.items():
    ind = compute_indicators(hist["Close"])
    st.subheader(t)

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**均線狀態**\n\n{ma_cross_status(ind)}")
    c2.markdown(f"**RSI(14)**\n\n{rsi_status(ind)}")
    c3.markdown(f"**MACD**\n\n{macd_status(ind)}")

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.5, 0.25, 0.25],
        vertical_spacing=0.04,
        subplot_titles=("價格與均線", "RSI(14)", "MACD"),
    )

    fig.add_trace(
        go.Scatter(x=ind.index, y=ind["close"], name="收盤價", line=dict(color=CATEGORICAL_COLORS[0], width=2)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=ind.index, y=ind["ma20"], name="MA20", line=dict(color=CATEGORICAL_COLORS[1], width=1.5)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=ind.index, y=ind["ma60"], name="MA60", line=dict(color=CATEGORICAL_COLORS[2], width=1.5)),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(x=ind.index, y=ind["rsi"], name="RSI", line=dict(color=CATEGORICAL_COLORS[3], width=1.5)),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#EF4444", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#10B981", row=2, col=1)

    fig.add_trace(
        go.Bar(x=ind.index, y=ind["macd_hist"], name="MACD 柱狀圖", marker_color="#9CA3AF"),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=ind.index, y=ind["macd"], name="MACD", line=dict(color=CATEGORICAL_COLORS[0], width=1.5)),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=ind.index, y=ind["macd_signal"], name="訊號線", line=dict(color=CATEGORICAL_COLORS[4], width=1.5)
        ),
        row=3,
        col=1,
    )

    fig.update_layout(height=700, hovermode="x unified", margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, width="stretch")
    st.divider()

st.caption("均線交叉、RSI、MACD 皆為歷史資料計算出的客觀技術指標，僅供參考，不構成投資建議。")
