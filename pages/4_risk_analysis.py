import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import DIVERGING_COLORSCALE, load_all_history, sidebar_period, sidebar_tickers

st.set_page_config(page_title="風險 / 相關性分析", page_icon="⚖️", layout="wide")
st.title("⚖️ 風險 / 相關性分析")
st.caption("波動率、最大回撤與標的間的相關係數，用來評估你手上持有的標的彼此分散程度。")

tickers = sidebar_tickers()
start_date, end_date = sidebar_period()

if len(tickers) < 1:
    st.info("請在左側輸入至少一個標的代碼。")
    st.stop()

data = load_all_history(tickers, start_date, end_date)
if not data:
    st.stop()

returns = {}
risk_rows = []
for t, hist in data.items():
    close = hist["Close"]
    daily_ret = close.pct_change().dropna()
    returns[t] = daily_ret

    annualized_vol = daily_ret.std() * np.sqrt(252) * 100
    running_max = close.cummax()
    drawdown = close / running_max - 1
    max_drawdown = drawdown.min() * 100

    risk_rows.append(
        {
            "標的": t,
            "年化波動率 %": round(annualized_vol, 2),
            "最大回撤 %": round(max_drawdown, 2),
        }
    )

st.subheader("風險指標")
st.dataframe(pd.DataFrame(risk_rows), width="stretch", hide_index=True)

if len(returns) >= 2:
    st.subheader("相關係數矩陣")
    ret_df = pd.DataFrame(returns).dropna()
    corr = ret_df.corr()

    fig = go.Figure(
        data=go.Heatmap(
            z=corr.values,
            x=corr.columns,
            y=corr.index,
            zmin=-1,
            zmax=1,
            colorscale=DIVERGING_COLORSCALE,
            text=corr.round(2).values,
            texttemplate="%{text}",
            hovertemplate="%{y} vs %{x}<br>相關係數: %{z:.2f}<extra></extra>",
            colorbar=dict(title="相關係數"),
        )
    )
    fig.update_layout(height=400 + 30 * len(corr), margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("相關係數越接近 1 代表兩個標的漲跌越同步（分散效果差），越接近 -1 代表走勢相反（分散效果好），接近 0 代表沒有明顯關聯。")
else:
    st.info("追蹤兩個以上標的才能看相關係數矩陣。")
