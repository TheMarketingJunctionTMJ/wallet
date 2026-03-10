import time
from datetime import datetime, timezone

import requests
import streamlit as st

st.set_page_config(
    page_title="Crypto P&L Tracker",
    page_icon="📈",
    layout="wide",
)

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

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
        font-size: 1.2rem;
        font-weight: 700;
    }
    .profit-box {
        background: #ecfdf3;
        color: #166534;
        border: 1px solid #bbf7d0;
        border-radius: 18px;
        padding: 18px;
        font-weight: 700;
        font-size: 1.35rem;
        text-align: center;
    }
    .loss-box {
        background: #fef2f2;
        color: #b91c1c;
        border: 1px solid #fecaca;
        border-radius: 18px;
        padding: 18px;
        font-weight: 700;
        font-size: 1.35rem;
        text-align: center;
    }
    .neutral-box {
        background: #f9fafb;
        color: #374151;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 18px;
        font-weight: 700;
        font-size: 1.35rem;
        text-align: center;
    }
    .small-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 14px 16px;
    }
    .subtle {
        color: #6b7280;
        font-size: 0.92rem;
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


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def fmt_money(value: float, digits: int = 4) -> str:
    return f"${value:,.{digits}f}"


def calculate_pnl(side: str, entry_price: float, current_price: float, quantity: float):
    if entry_price <= 0 or quantity <= 0:
        return 0.0, 0.0

    if side == "Long":
        pnl = (current_price - entry_price) * quantity
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
    else:
        pnl = (entry_price - current_price) * quantity
        pnl_pct = ((entry_price - current_price) / entry_price) * 100

    return pnl, pnl_pct


def render_pnl_box(pnl_value: float):
    if pnl_value > 0:
        st.markdown(f'<div class="profit-box">{fmt_money(pnl_value)}</div>', unsafe_allow_html=True)
    elif pnl_value < 0:
        st.markdown(f'<div class="loss-box">{fmt_money(pnl_value)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="neutral-box">{fmt_money(pnl_value)}</div>', unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_markets(vs_currency: str = "usd", per_page: int = 250):
    all_rows = []
    for page in range(1, 5):
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        response = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=20)
        response.raise_for_status()
        rows = response.json()
        if not rows:
            break
        all_rows.extend(rows)
    return all_rows


try:
    market_rows = fetch_markets()
except Exception as exc:
    st.error(f"Could not load crypto market data: {exc}")
    st.stop()

coin_options = []
coin_map = {}

for row in market_rows:
    label = f"{row['symbol'].upper()} — {row['name']}"
    coin_options.append(label)
    coin_map[label] = row

default_label = next((x for x in coin_options if x.startswith("BTC ")), coin_options[0])

st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">Live Crypto Price Tracker</div>
        <h1>Crypto P&L Dashboard</h1>
        <p>Track live market prices, enter your long or short position, and monitor real-time profit and loss on Streamlit Cloud.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("Settings")
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_seconds = st.selectbox("Refresh every", [5, 10, 15, 30, 60], index=1)
    search_text = st.text_input("Search coin", placeholder="BTC, ETH, SOL")
    st.markdown("---")
    st.caption("Data source: CoinGecko market data")
    st.caption("This version supports long and short P&L.")
    st.caption("It does not calculate exchange fees, leverage, or liquidation.")

filtered_options = [
    option for option in coin_options
    if search_text.strip().lower() in option.lower()
] or coin_options

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Coins Loaded</div><div class="metric-value">{len(market_rows):,}</div></div>',
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        '<div class="metric-card"><div class="metric-label">Data Source</div><div class="metric-value">CoinGecko</div></div>',
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
    selected_label = st.selectbox(
        "Crypto",
        filtered_options,
        index=filtered_options.index(default_label) if default_label in filtered_options else 0,
    )
    selected = coin_map[selected_label]

    current_price = float(selected.get("current_price") or 0.0)
    quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.001, format="%.6f")
    entry_price = st.number_input("Entry price", min_value=0.0, value=current_price, step=0.01, format="%.8f")

    pnl_value, pnl_pct = calculate_pnl(position_side, entry_price, current_price, quantity)
    cost_basis = entry_price * quantity
    current_value = current_price * quantity
    raw_move = current_price - entry_price

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
        change_24h = float(selected.get("price_change_percentage_24h") or 0.0)
        st.markdown(
            f"""
            <div class="small-card">
                <div class="subtle">24h Change</div>
                <div><strong>{change_24h:,.2f}%</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown("#### Unrealized P&L")
    render_pnl_box(pnl_value)

    p1, p2 = st.columns(2)
    with p1:
        st.metric("P&L %", f"{pnl_pct:,.2f}%")
    with p2:
        status = "Profit" if pnl_value > 0 else "Loss" if pnl_value < 0 else "Flat"
        st.metric("Status", status)

    st.markdown("")
    p3, p4 = st.columns(2)
    with p3:
        st.metric("Cost Basis", fmt_money(cost_basis, 4))
        st.metric("Current Value", fmt_money(current_value, 4))
        st.metric("Position Side", position_side)
    with p4:
        st.metric("Market Cap Rank", f"#{selected.get('market_cap_rank', '-')}")
        st.metric("Raw Price Move", fmt_money(raw_move, 6))
        st.metric("Symbol", selected.get("symbol", "").upper())

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Live Market Table")

    table_rows = []
    for row in market_rows:
        if search_text.strip() and search_text.strip().lower() not in f"{row['symbol']} {row['name']}".lower():
            continue
        table_rows.append(
            {
                "Symbol": row["symbol"].upper(),
                "Name": row["name"],
                "Price": row["current_price"],
                "24h %": row.get("price_change_percentage_24h"),
                "Market Cap Rank": row.get("market_cap_rank"),
            }
        )

    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="%.8f"),
            "24h %": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("")
st.caption(
    "This app uses CoinGecko live crypto market data and calculates simple unrealized P&L for long and short positions. It does not include fees, leverage, liquidation, or exchange-specific futures mechanics."
)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
