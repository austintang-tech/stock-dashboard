import pandas as pd
import streamlit as st
import yfinance as yf
from datetime import date, timedelta

DEFAULT_TICKERS = ["0050.TW", "0056.TW", "00878.TW", "2330.TW"]
CATEGORICAL_COLORS = ["#3B82F6", "#F59E0B", "#10B981", "#8B5CF6", "#EF4444", "#06B6D4"]
DIVERGING_COLORSCALE = [[0, "#EF4444"], [0.5, "#9CA3AF"], [1, "#3B82F6"]]

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
    price_cols = ["Open", "High", "Low", "Close"]
    df[price_cols] = df[price_cols].ffill()
    df = df.dropna(subset=["Close"])
    return df


@st.cache_data(ttl=3600)
def fetch_dividends(ticker: str) -> pd.Series:
    div = yf.Ticker(ticker).dividends
    if len(div):
        div.index = div.index.tz_localize(None)
    return div


@st.cache_data(ttl=1800)
def fetch_news(ticker: str) -> list:
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    items = []
    for entry in raw:
        c = entry.get("content", {})
        url = (c.get("canonicalUrl") or c.get("clickThroughUrl") or {}).get("url", "")
        items.append(
            {
                "ticker": ticker,
                "title": c.get("title", ""),
                "publisher": (c.get("provider") or {}).get("displayName", ""),
                "pub_date": c.get("pubDate", ""),
                "url": url,
            }
        )
    return items


def sidebar_tickers() -> list[str]:
    if "tickers_input" not in st.session_state:
        st.session_state["tickers_input"] = "\n".join(DEFAULT_TICKERS)
    with st.sidebar:
        st.header("追蹤標的")
        tickers_input = st.text_area(
            "每行一個，台股請加 .TW，例如 0050.TW",
            key="tickers_input",
            height=100,
        )
        if st.button("清除快取並重新抓取"):
            st.cache_data.clear()
    return [t.strip().upper() for t in tickers_input.splitlines() if t.strip()]


def sidebar_period(default_index: int = 2):
    if "period_select" not in st.session_state:
        st.session_state["period_select"] = list(PERIOD_OPTIONS.keys())[default_index]
    with st.sidebar:
        label = st.selectbox("時間範圍", list(PERIOD_OPTIONS.keys()), key="period_select")
    days = PERIOD_OPTIONS[label]
    return date.today() - timedelta(days=days), date.today() + timedelta(days=1)


def load_all_history(tickers: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    data = {}
    for t in tickers:
        hist = fetch_history(t, start, end)
        if hist.empty:
            st.warning(f"抓不到「{t}」的資料，請確認代碼是否正確（台股例如 0050.TW）。")
            continue
        data[t] = hist
    return data
