import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import requests
import streamlit as st

st.set_page_config(
    page_title="Binance Futures P&L Tracker",
    page_icon="📈",
    layout="wide",
)

BASE_URL = "https://fapi.binance.com"
SYMBOLS_URL = f"{BASE_URL}/fapi/v1/exchangeInfo"
PRICES_URL = f"{BASE_URL}/fapi/v2/ticker/price"
MARK_PRICE_URL = f"{BASE_URL}/fapi/v1/premiumIndex"

CUSTOM_CSS = """
<style>
    .stApp {
        background: #f6f8fb;
    }

    .block-container {
        max-width: 1380px;
        padding-top: 1.6rem;
        padding-bottom: 2rem;
    }

    .hero {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 24px;
        padding: 28px 30px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        margin-bottom: 1rem;
    }

    .hero h1 {
        margin: 0;
        color: #111827;
        font-size: 2.2rem;
        font-weight: 800;
    }

    .hero p {
        margin: 0.55rem 0 0;
        color: #4b5563;
        font-size: 1rem;
    }

    .eyebrow {
        display: inline-block;
        margin-bottom: 10px;
        color: #2563eb;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 22px;
        padding: 22px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }

    .metric-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
    }

    .metric-label {
        color: #6b7280;
        font-size: 0.86rem;
        margin-bottom: 0.25rem;
    }

    .metric-value {
        color: #111827;
        font-size: 1.28rem;
        font-weight: 700;
    }

    .profit-box {
        background: #ecfdf3;
        color: #166534;
        border: 1px solid #bbf7d0;
        border-radius: 18px;
        padding: 18px;
        font-weight: 700;
        font-size: 1.4rem;
        text-align: center;
    }

    .loss-box {
        background: #fef2f2;
        color: #b91c1c;
        border: 1px solid #fecaca;
        border-radius: 18px;
        padding: 18px;
        font-weight: 700;
        font-size: 1.4rem;
        text-align: center;
    }

    .neutral-box {
        background: #f9fafb;
        color: #374151;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 18px;
        font-weight: 700;
        font-size: 1.4rem;
        text-align: center;
    }

    .subtle {
        color: #6b7280;
        font-size: 0.92rem;
    }

    .small-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 14px 16px;
    }

    div[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-baseweb="select"] > div {
        border-radius: 12px !important;
    }

    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def fmt_num(value: float, digits: int = 4) -> str:
    return f"{value:,.{digits}f}"


def fmt_money(value: float, digits: int = 4) -> str:
    return f"${value:,.{digits}f}"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_symbols() -> List[Dict]:
    resp = requests.get(SYMBOLS_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    symbols = []
    for s in data.get("symbols", []):
        if (
            s.get("status") == "TRADING"
            and s.get("contractType") == "PERPETUAL"
            and s.get("quoteAsset") in {"USDT", "USDC", "BUSD"}
        ):
            symbols.append(
                {
                    "symbol": s.get("symbol"),
                    "baseAsset": s.get("baseAsset"),
                    "quoteAsset": s.get("quoteAsset"),
                }
            )

    symbols.sort(key=lambda x: x["symbol"])
    return symbols


@st.cache_data(ttl=2, show_spinner=False)
def fetch_all_prices() -> Dict[str, float]:
    resp = requests.get(PRICES_URL, timeout=20)
    resp.raise_for_status()
    rows = resp.json()
    return {row["symbol"]: float(row["price"]) for row in rows}


@st.cache_data(ttl=2, show_spinner=False)
def fetch_all_mark_prices() -> Dict[str, Dict]:
    resp = requests.get(MARK_PRICE_URL, timeout=20)
    resp.raise_for_status()
    rows = resp.json()
    if isinstance(rows, dict):
        rows = [rows]

    result = {}
    for row in rows:
        result[row["symbol"]] = {
            "markPrice": float(row["markPrice"]),
            "indexPrice": float(row["indexPrice"]),
            "lastFundingRate": float(row["lastFundingRate"]),
            "nextFundingTime": int(row["nextFundingTime"]),
            "time": int(row["time"]),
        }
    return result


def calculate_pnl(side: str, entry_price: float, current_price: float, quantity: float) -> Tuple[float, float]:
    if entry_price <= 0 or quantity <= 0:
        return 0.0, 0.0

    if side == "Long":
        pnl = (current_price - entry_price) * quantity
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
    else:
        pnl = (entry_price - current_price) * quantity
        pnl_pct = ((entry_price - current_price) / entry_price) * 100

    return pnl, pnl_pct


def render_pnl_box(pnl_value: float) -> None:
    if pnl_value > 0:
        st.markdown(f'<div class="profit-box">{fmt_money(pnl_value)}</div>', unsafe_allow_html=True)
    elif pnl_value < 0:
        st.markdown(f'<div class="loss-box">{fmt_money(pnl_value)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="neutral-box">{fmt_money(pnl_value)}</div>', unsafe_allow_html=True)


def build_market_table(
    symbols: List[Dict],
    prices: Dict[str, float],
    marks: Dict[str, Dict],
    quote_filter: str,
    search_text: str,
) -> List[Dict]:
    rows = []
    search_text = search_text.strip().upper()

    for s in symbols:
        symbol = s["symbol"]
        quote = s["quoteAsset"]

        if quote_filter != "ALL" and quote != quote_filter:
            continue
        if search_text and search_text not in symbol:
            continue
        if symbol not in prices:
            continue

        mark = marks.get(symbol, {})
        rows.append(
            {
                "Symbol": symbol,
                "Base": s["baseAsset"],
                "Quote": quote,
                "Last Price": prices.get(symbol),
                "Mark Price": mark.get("markPrice"),
                "Funding Rate": mark.get("lastFundingRate"),
            }
        )

    return rows


st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">Live Binance Futures Tracker</div>
        <h1>Binance Futures P&L Dashboard</h1>
        <p>Track live USDⓈ-M perpetual futures prices, enter your long or short position, and monitor real-time profit and loss.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("Settings")

    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_seconds = st.selectbox("Refresh every", [2, 3, 5, 10, 15, 30], index=2)
    quote_filter = st.selectbox("Quote filter", ["ALL", "USDT", "USDC", "BUSD"], index=0)
    search_text = st.text_input("Search symbol", placeholder="BTC or BTCUSDT")

    st.markdown("---")
    st.markdown("**Notes**")
    st.caption("Tracks active USDⓈ-M perpetual futures.")
    st.caption("Supports both long and short positions.")
    st.caption("P&L shown here does not include fees or funding settlement impact.")

try:
    symbols = fetch_symbols()
    prices = fetch_all_prices()
    marks = fetch_all_mark_prices()
except Exception as exc:
    st.error(f"Could not load Binance market data: {exc}")
    st.stop()

symbol_options = [s["symbol"] for s in symbols]
default_symbol = "BTCUSDT" if "BTCUSDT" in symbol_options else symbol_options[0]

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Contracts Loaded</div><div class="metric-value">{len(symbols):,}</div></div>',
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        '<div class="metric-card"><div class="metric-label">Market Type</div><div class="metric-value">USDⓈ-M Perpetual</div></div>',
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Auto Refresh</div><div class="metric-value">{"On" if auto_refresh else "Off"}</div></div>',
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Last Update</div><div class="metric-value" style="font-size:0.95rem;">{now_utc()}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("")

left, right = st.columns([0.95, 1.05], gap="large")

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Your Position")

    position_side = st.radio("Position side", ["Long", "Short"], horizontal=True)
    symbol = st.selectbox("Futures contract", symbol_options, index=symbol_options.index(default_symbol))
    quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.001, format="%.6f")
    entry_price = st.number_input("Entry price", min_value=0.0, value=prices.get(symbol, 0.0), step=0.01, format="%.8f")

    current_price = prices.get(symbol, 0.0)
    mark_data = marks.get(symbol, {})
    mark_price = mark_data.get("markPrice", current_price)
    index_price = mark_data.get("indexPrice", current_price)
    funding_rate = mark_data.get("lastFundingRate", 0.0)

    pnl_value, pnl_pct = calculate_pnl(position_side, entry_price, current_price, quantity)
    pnl_mark_value, pnl_mark_pct = calculate_pnl(position_side, entry_price, mark_price, quantity)

    notional_value = current_price * quantity
    entry_notional = entry_price * quantity
    price_move = current_price - entry_price

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
            <div class="small-card">
                <div class="subtle">Current Price</div>
                <div><strong>{fmt_money(current_price, 6)}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="small-card">
                <div class="subtle">Mark Price</div>
                <div><strong>{fmt_money(mark_price, 6)}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown("#### Unrealized P&L (Last Price)")
    render_pnl_box(pnl_value)

    p1, p2 = st.columns(2)
    with p1:
        st.metric("P&L %", f"{pnl_pct:,.2f}%")
    with p2:
        label = "Profit" if pnl_value > 0 else "Loss" if pnl_value < 0 else "Flat"
        st.metric("Status", label)

    st.markdown("")
    st.markdown("#### Unrealized P&L (Mark Price)")
    render_pnl_box(pnl_mark_value)

    p3, p4 = st.columns(2)
    with p3:
        st.metric("Mark P&L %", f"{pnl_mark_pct:,.2f}%")
    with p4:
        st.metric("Funding Rate", f"{funding_rate * 100:.4f}%")

    st.markdown("")
    i1, i2 = st.columns(2)
    with i1:
        st.metric("Entry Notional", fmt_money(entry_notional, 4))
        st.metric("Current Notional", fmt_money(notional_value, 4))
        st.metric("Position Side", position_side)
    with i2:
        st.metric("Index Price", fmt_money(index_price, 6))
        st.metric("Raw Price Move", fmt_money(price_move, 6))
        st.metric("Symbol", symbol)

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Live Futures Market")

    rows = build_market_table(
        symbols=symbols,
        prices=prices,
        marks=marks,
        quote_filter=quote_filter,
        search_text=search_text,
    )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Last Price": st.column_config.NumberColumn(format="%.8f"),
            "Mark Price": st.column_config.NumberColumn(format="%.8f"),
            "Funding Rate": st.column_config.NumberColumn(format="%.6f"),
        },
    )

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("")
st.caption(
    "This app uses Binance public USDⓈ-M Futures market data and calculates simple unrealized P&L for long and short positions. It does not include fees, realized P&L, liquidation mechanics, margin mode effects, or funding payments."
)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
