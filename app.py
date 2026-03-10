import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
import streamlit as st

st.set_page_config(
    page_title="Crypto P&L Tracker",
    page_icon="📈",
    layout="wide",
)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINS_LIST_URL = f"{COINGECKO_BASE}/coins/list"
SIMPLE_PRICE_URL = f"{COINGECKO_BASE}/simple/price"
MARKETS_URL = f"{COINGECKO_BASE}/coins/markets"

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
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def fmt_money(value: float, digits: int = 4) -> str:
    return f"${value:,.{digits}f}"


def get_demo_key() -> str:
    return st.secrets.get("COINGECKO_DEMO_API_KEY", "")


def cg_headers() -> Dict[str, str]:
    demo_key = get_demo_key()
    headers = {"accept": "application/json"}
    if demo_key:
        headers["x-cg-demo-api-key"] = demo_key
    return headers


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


def safe_get(url: str, params: Optional[Dict] = None) -> requests.Response:
    response = requests.get(url, params=params, headers=cg_headers(), timeout=20)
    response.raise_for_status()
    return response


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_coin_list() -> List[Dict]:
    response = safe_get(COINS_LIST_URL)
    rows = response.json()

    # Deduplicate by id and keep simple label
    seen = set()
    cleaned = []
    for row in rows:
        coin_id = row.get("id")
        symbol = (row.get("symbol") or "").upper()
        name = row.get("name") or ""
        if not coin_id or coin_id in seen:
            continue
        seen.add(coin_id)
        cleaned.append(
            {
                "id": coin_id,
                "symbol": symbol,
                "name": name,
                "label": f"{symbol} — {name}",
            }
        )

    cleaned.sort(key=lambda x: (x["symbol"], x["name"]))
    return cleaned


@st.cache_data(ttl=15, show_spinner=False)
def fetch_top_markets(vs_currency: str = "usd", per_page: int = 50) -> List[Dict]:
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    response = safe_get(MARKETS_URL, params=params)
    return response.json()


@st.cache_data(ttl=10, show_spinner=False)
def fetch_selected_price(coin_id: str, vs_currency: str = "usd") -> Dict:
    params = {
        "ids": coin_id,
        "vs_currencies": vs_currency,
        "include_24hr_change": "true",
        "include_market_cap": "true",
        "include_last_updated_at": "true",
    }
    response = safe_get(SIMPLE_PRICE_URL, params=params)
    data = response.json()
    return data.get(coin_id, {})


st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">Live Crypto Price Tracker</div>
        <h1>Crypto P&L Dashboard</h1>
        <p>Track live prices, enter your long or short position, and monitor real-time profit and loss with a lighter API footprint.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("Settings")
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_seconds = st.selectbox("Refresh every", [10, 15, 30, 60], index=1)
    search_text = st.text_input("Search coin", placeholder="BTC, ETH, SOL")
    st.markdown("---")
    if get_demo_key():
        st.success("CoinGecko demo key detected.")
    else:
        st.warning("No CoinGecko demo key found. Public access may hit rate limits on Streamlit Cloud.")
    st.caption("Optional Streamlit secret:")
    st.code('COINGECKO_DEMO_API_KEY = "your_demo_key_here"', language="toml")

try:
    coin_list = fetch_coin_list()
    top_markets = fetch_top_markets()
except requests.HTTPError as exc:
    if exc.response is not None and exc.response.status_code == 429:
        st.error(
            "CoinGecko rate limit hit. Add a CoinGecko demo key in Streamlit Secrets and redeploy, "
            "or turn off auto-refresh and wait a minute."
        )
    else:
        st.error(f"Could not load crypto market data: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Could not load crypto market data: {exc}")
    st.stop()

filtered_coins = [
    coin for coin in coin_list
    if search_text.strip().lower() in coin["label"].lower()
] or coin_list

default_label = next((c["label"] for c in filtered_coins if c["symbol"] == "BTC"), filtered_coins[0]["label"])
selected_label = st.session_state.get("selected_label", default_label)

label_to_coin = {coin["label"]: coin for coin in filtered_coins}
if selected_label not in label_to_coin:
    selected_label = filtered_coins[0]["label"]

selected_coin = label_to_coin[selected_label]

try:
    selected_price = fetch_selected_price(selected_coin["id"])
except requests.HTTPError as exc:
    if exc.response is not None and exc.response.status_code == 429:
        st.error(
            "CoinGecko rate limit hit while fetching the selected coin. "
            "Try again shortly, reduce refresh frequency, or use a CoinGecko demo key."
        )
    else:
        st.error(f"Could not load selected coin price: {exc}")
    st.stop()

current_price = float(selected_price.get("usd", 0.0))
change_24h = float(selected_price.get("usd_24h_change", 0.0) or 0.0)
market_cap = float(selected_price.get("usd_market_cap", 0.0) or 0.0)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Coins Loaded</div><div class="metric-value">{len(coin_list):,}</div></div>',
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
    chosen_label = st.selectbox(
        "Crypto",
        [coin["label"] for coin in filtered_coins],
        index=[coin["label"] for coin in filtered_coins].index(selected_label),
    )
    st.session_state["selected_label"] = chosen_label
    selected_coin = label_to_coin[chosen_label]

    # Re-fetch only if changed after initial load
    if selected_coin["id"] != coin_list[[c["label"] for c in coin_list].index(selected_label)]["id"]:
        selected_price = fetch_selected_price(selected_coin["id"])
        current_price = float(selected_price.get("usd", 0.0))
        change_24h = float(selected_price.get("usd_24h_change", 0.0) or 0.0)
        market_cap = float(selected_price.get("usd_market_cap", 0.0) or 0.0)

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
        st.metric("Market Cap", fmt_money(market_cap, 0))
        st.metric("Raw Price Move", fmt_money(raw_move, 6))
        st.metric("Symbol", selected_coin["symbol"])

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Top Market Table")

    table_rows = []
    search_lower = search_text.strip().lower()

    for row in top_markets:
        text = f"{row.get('symbol', '')} {row.get('name', '')}".lower()
        if search_lower and search_lower not in text:
            continue
        table_rows.append(
            {
                "Symbol": (row.get("symbol") or "").upper(),
                "Name": row.get("name"),
                "Price": row.get("current_price"),
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
    "This version uses a lower-request design: cached coin list, one top-market request, and one selected-price request. "
    "It supports long and short unrealized P&L, but not leverage, fees, or liquidation logic."
)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
