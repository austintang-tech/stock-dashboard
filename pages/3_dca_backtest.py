from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from common import CATEGORICAL_COLORS, fetch_dividends, fetch_history, sidebar_tickers

st.set_page_config(page_title="定期定額回測試算器", page_icon="🧮", layout="wide")
st.title("🧮 定期定額回測試算器")
st.caption("模擬「每月固定投入金額買進、配息全部再投入」的歷史結果，用於比較不同標的的定期定額效果。此為歷史資料模擬，不代表未來績效，不構成投資建議。")

tickers = sidebar_tickers()
if not tickers:
    st.info("請在左側輸入至少一個標的代碼。")
    st.stop()

with st.sidebar:
    st.header("定期定額設定")
    monthly_amount = st.number_input("每月投入金額", min_value=100, value=5000, step=500)
    years_back = st.slider("回測年數", min_value=1, max_value=15, value=5)
    buy_day = st.slider("每月扣款日", min_value=1, max_value=28, value=5)
    reinvest = st.checkbox("配息再投入", value=True)

sim_start = date.today().replace(year=date.today().year - years_back)
sim_end = date.today()


def compute_xirr(dates: list, amounts: list) -> float:
    dates = pd.to_datetime(pd.Series(dates))
    t0 = dates.iloc[0]
    days = (dates - t0).dt.days.values

    def npv(rate):
        return sum(a / (1 + rate) ** (d / 365) for a, d in zip(amounts, days))

    lo, hi = -0.9, 5.0
    if npv(lo) < 0 or npv(hi) > 0:
        return float("nan")
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return mid


def simulate_dca(ticker: str, start: date, end: date, monthly_amount: float, buy_day: int, reinvest: bool):
    hist = fetch_history(ticker, start, end)
    if hist.empty:
        return None
    div = fetch_dividends(ticker)
    div = div[(div.index >= pd.Timestamp(start)) & (div.index <= pd.Timestamp(end))]

    purchase_targets = pd.date_range(start=start, end=end, freq="MS") + pd.Timedelta(days=buy_day - 1)

    events = []  # (date, type, amount) type: "buy" (fixed cash) or "dividend"
    for pt in purchase_targets:
        idx = hist.index.searchsorted(pt)
        if idx < len(hist.index):
            events.append((hist.index[idx], "buy", monthly_amount))
    if reinvest:
        for d_date, amt in div.items():
            idx = hist.index.searchsorted(d_date)
            if idx < len(hist.index):
                events.append((hist.index[idx], "dividend", amt))
    events.sort(key=lambda e: e[0])

    shares = 0.0
    invested = 0.0
    cashflow_dates = []
    cashflow_amounts = []
    shares_series = pd.Series(0.0, index=hist.index)

    for ev_date, ev_type, amount in events:
        price = hist.loc[ev_date, "Close"]
        if ev_type == "buy":
            shares += amount / price
            invested += amount
            cashflow_dates.append(ev_date)
            cashflow_amounts.append(-amount)
        else:
            shares += (amount * shares) / price
        shares_series.loc[ev_date] = shares

    shares_series = shares_series.replace(0.0, pd.NA).ffill().fillna(0.0)
    portfolio_value = shares_series * hist["Close"]

    final_value = portfolio_value.iloc[-1]
    cashflow_dates.append(hist.index[-1])
    cashflow_amounts.append(final_value)
    irr = compute_xirr(cashflow_dates, cashflow_amounts)

    return {
        "ticker": ticker,
        "invested": invested,
        "final_value": final_value,
        "total_return_pct": (final_value / invested - 1) * 100 if invested else 0,
        "annualized_return_pct": irr * 100 if pd.notna(irr) else float("nan"),
        "portfolio_value": portfolio_value,
        "invested_series": pd.Series(
            [monthly_amount * i for i in range(1, len(purchase_targets) + 1)],
            index=[e[0] for e in events if e[1] == "buy"][: len(purchase_targets)],
        ).reindex(hist.index, method="ffill").fillna(0.0),
    }


results = []
for t in tickers:
    r = simulate_dca(t, sim_start, sim_end, monthly_amount, buy_day, reinvest)
    if r:
        results.append(r)

if not results:
    st.warning("沒有足夠的資料可以模擬，請確認標的代碼或縮短回測年數。")
    st.stop()

st.subheader("回測結果總覽")
summary = pd.DataFrame(
    [
        {
            "標的": r["ticker"],
            "累計投入": f"{r['invested']:,.0f}",
            "期末價值": f"{r['final_value']:,.0f}",
            "總報酬率 %": round(r["total_return_pct"], 2),
            "年化報酬率 % (XIRR)": round(r["annualized_return_pct"], 2) if pd.notna(r["annualized_return_pct"]) else "N/A",
        }
        for r in results
    ]
)
st.dataframe(summary, width="stretch", hide_index=True)

st.subheader("資產成長曲線")
fig = go.Figure()
for i, r in enumerate(results):
    color = CATEGORICAL_COLORS[i % len(CATEGORICAL_COLORS)]
    fig.add_trace(
        go.Scatter(
            x=r["portfolio_value"].index,
            y=r["portfolio_value"].values,
            name=f"{r['ticker']} 資產價值",
            line=dict(color=color, width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=r["invested_series"].index,
            y=r["invested_series"].values,
            name=f"{r['ticker']} 累計投入",
            line=dict(color=color, width=1, dash="dot"),
        )
    )
fig.update_layout(
    height=500,
    hovermode="x unified",
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    yaxis_title="金額 (TWD)",
)
st.plotly_chart(fig, width="stretch")

st.caption("實線＝模擬資產價值（含配息再投入），虛線＝累計投入成本。假設可買進小數股數，僅為概念性模擬。")
