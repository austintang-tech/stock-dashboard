import streamlit as st
import pandas as pd

from common import sidebar_tickers, fetch_news

st.set_page_config(page_title="新聞整合牆", page_icon="📰", layout="wide")
st.title("📰 新聞整合牆")
st.caption("把所有追蹤標的的最新相關新聞集中在一個地方。ETF 通常沒有專屬新聞，個股（如 2330.TW）才會有。")

tickers = sidebar_tickers()

if not tickers:
    st.info("請在左側輸入至少一個標的代碼。")
    st.stop()

all_news = []
for t in tickers:
    all_news.extend(fetch_news(t))

if not all_news:
    st.info("目前抓不到任何追蹤標的的新聞。")
    st.stop()

df = pd.DataFrame(all_news)
df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce", utc=True)
df = df.sort_values("pub_date", ascending=False).drop_duplicates(subset="title")

tag_filter = st.multiselect("篩選標的", options=sorted(df["ticker"].unique()), default=[])
if tag_filter:
    df = df[df["ticker"].isin(tag_filter)]

for _, row in df.iterrows():
    pub = row["pub_date"]
    pub_str = pub.tz_convert("Asia/Taipei").strftime("%Y-%m-%d %H:%M") if pd.notna(pub) else ""
    st.markdown(
        f"**[{row['title']}]({row['url']})**  \n"
        f"`{row['ticker']}` · {row['publisher']} · {pub_str}"
    )
    st.divider()
