import os
import sys
import time
import pandas as pd
import streamlit as st
from sqlalchemy import select

# Add parent directory to path to import atc module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from atc.config import get_settings
from atc.db import make_session, Candle, Signal, PaperTrade, PaperPosition
from atc.binance_client import SimpleBinance


st.set_page_config(page_title="ATC Monitor", layout="wide")
s = get_settings()

st.sidebar.header("Settings")
st.sidebar.write(f"Mode: {s.mode}")
st.sidebar.write(f"Market: {s.market}")
st.sidebar.write(f"Symbol: {s.symbol}")
st.sidebar.write(f"Interval: {s.interval}")


@st.cache_data(ttl=10)
def load_df(n=300):
    session = make_session(s.db_path)
    try:
        rows = (
            session.execute(
                select(Candle)
                .where((Candle.symbol == s.symbol) & (Candle.interval == s.interval))
                .order_by(Candle.open_time.desc())
                .limit(n)
            )
            .scalars()
            .all()
        )
        rows = list(reversed(rows))
        df = pd.DataFrame(
            [
                {
                    "open_time": r.open_time,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                }
                for r in rows
            ]
        )
        return df
    finally:
        session.close()


@st.cache_data(ttl=5)
def load_signals(n=50):
    session = make_session(s.db_path)
    try:
        rows = (
            session.execute(select(Signal).order_by(Signal.ts.desc()).limit(n)).scalars().all()
        )
        df = pd.DataFrame(
            [
                {
                    "ts": r.ts,
                    "symbol": r.symbol,
                    "action": r.action,
                    "confidence": r.confidence,
                    "size_usdt": r.size_usdt,
                    "reason": r.reason,
                }
                for r in rows
            ]
        )
        return df
    finally:
        session.close()


def load_paper():
    session = make_session(s.db_path)
    try:
        pos = session.execute(select(PaperPosition)).scalars().all()
        trades = session.execute(select(PaperTrade).order_by(PaperTrade.ts.desc()).limit(100)).scalars().all()
        return pos, trades
    finally:
        session.close()


left, right = st.columns([2, 1])
with left:
    st.header("Market")
    df = load_df()
    if not df.empty:
        st.line_chart(df.set_index("open_time")["close"], height=300)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Latest Signals")
        sigs = load_signals()
        st.dataframe(sigs, height=300)
    with col2:
        st.subheader("Now")
        try:
            price = SimpleBinance(futures=(s.market == "futures")).ticker_price(s.symbol)
            st.metric("Price", f"{price:,.2f} USDT")
        except Exception as e:
            st.write(f"Price error: {e}")

with right:
    st.header("Paper Trading")
    pos, trades = load_paper()
    if pos:
        st.subheader("Positions")
        dfp = pd.DataFrame([{"symbol": p.symbol, "qty": p.qty, "entry_price": p.entry_price} for p in pos])
        st.dataframe(dfp, height=150)
    if trades:
        st.subheader("Recent Trades")
        dft = pd.DataFrame(
            [
                {"ts": t.ts, "symbol": t.symbol, "side": t.side, "qty": t.qty, "price": t.price, "pnl": t.pnl_usdt}
                for t in trades
            ]
        )
        st.dataframe(dft, height=350)

st.caption("Refresh the page to update cached data.")

