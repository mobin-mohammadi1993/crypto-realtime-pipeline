"""
Live price/volume dashboard.

Layout: a grid of glass cards, one per coin (20 of them, five per row),
each with a sparkline and its current price. Clicking a card selects it,
and the detail panel below expands to show that one coin's full chart,
volume, and stats.

Auto-refresh uses st.fragment(run_every=...) instead of a full-script
rerun loop. A fragment is a chunk of the page Streamlit can re-execute on
its own timer *without* tearing down and repainting the whole app, so the
five-second refresh updates numbers in place instead of flashing the
whole page blank and back.
"""
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine

PG_URL = os.getenv("PG_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/warehouse")
REFRESH_SECONDS = 5
CARDS_PER_ROW = 5

# 20 coins, each with a fixed color and label so identity never depends
# on color alone -- every card and chart also carries the symbol as text.
COIN_STYLE = {
    "BTCUSDT": {"color": "#E69F00", "label": "Bitcoin"},
    "ETHUSDT": {"color": "#56B4E9", "label": "Ethereum"},
    "BNBUSDT": {"color": "#D55E00", "label": "BNB"},
    "SOLUSDT": {"color": "#009E73", "label": "Solana"},
    "XRPUSDT": {"color": "#CC79A7", "label": "XRP"},
    "ADAUSDT": {"color": "#4C72B0", "label": "Cardano"},
    "DOGEUSDT": {"color": "#F0C808", "label": "Dogecoin"},
    "TRXUSDT": {"color": "#C44E52", "label": "TRON"},
    "DOTUSDT": {"color": "#8172B3", "label": "Polkadot"},
    "LTCUSDT": {"color": "#B0B0B8", "label": "Litecoin"},
    "BCHUSDT": {"color": "#64B5CD", "label": "Bitcoin Cash"},
    "AVAXUSDT": {"color": "#E24A4A", "label": "Avalanche"},
    "LINKUSDT": {"color": "#2B6CB0", "label": "Chainlink"},
    "ATOMUSDT": {"color": "#6C5CE7", "label": "Cosmos"},
    "XLMUSDT": {"color": "#00B8A9", "label": "Stellar"},
    "ETCUSDT": {"color": "#55A630", "label": "Ethereum Classic"},
    "NEARUSDT": {"color": "#17C3B2", "label": "NEAR"},
    "UNIUSDT": {"color": "#FF6B9D", "label": "Uniswap"},
    "FILUSDT": {"color": "#4381C1", "label": "Filecoin"},
    "APTUSDT": {"color": "#22D3EE", "label": "Aptos"},
}

st.set_page_config(page_title="Crypto Real-Time Dashboard", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
    <style>
    /* One quiet teal glow, not a rainbow of them -- a real glass fintech
       UI leans on restraint: mostly neutral dark surfaces, with color
       spent only on the signal that matters (price up/down), not on
       every card having its own hue. */
    .stApp {
        background:
            radial-gradient(circle at 15% 0%, rgba(45,212,191,0.10) 0%, transparent 45%),
            radial-gradient(circle at 100% 100%, rgba(45,212,191,0.06) 0%, transparent 50%),
            #0b0e14;
    }

    .block-container { padding-top: 2.5rem; padding-bottom: 3rem; }

    /* Every st.container(border=True) becomes a frosted glass panel:
       translucent fill + backdrop blur + soft edge, instead of a flat
       dark box. Used for both the coin cards and the detail panel. */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 20px !important;
        border: 1px solid rgba(255,255,255,0.09) !important;
        background: rgba(255,255,255,0.035) !important;
        backdrop-filter: blur(22px);
        -webkit-backdrop-filter: blur(22px);
        box-shadow: 0 6px 24px rgba(0,0,0,0.3);
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 32px rgba(0,0,0,0.4);
        border-color: rgba(255,255,255,0.18) !important;
    }
    /* Extra breathing room inside every card/panel. */
    [data-testid="stVerticalBlockBorderWrapper"] > div { padding: 4px; }

    div.stButton > button {
        width: 100%;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.10);
        background: rgba(255,255,255,0.04);
        color: #a8adba;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.01em;
    }
    div.stButton > button:hover {
        border-color: rgba(45,212,191,0.5);
        background: rgba(45,212,191,0.08);
        color: #ffffff;
    }

    h1, h2, h3 { letter-spacing: -0.01em; }
    </style>
    """,
    unsafe_allow_html=True,
)

UP, DOWN = "#22c55e", "#ef4444"


def trend_color(df):
    return UP if df["avg_price"].iloc[-1] >= df["avg_price"].iloc[0] else DOWN


def load(query, params=None):
    engine = create_engine(PG_URL)
    return pd.read_sql(query, engine, params=params)


def sparkline(df, color):
    """A tiny, axis-free line chart for the card grid. spline = smooth
    curve through the points instead of straight sharp-angled segments."""
    fig = go.Figure(go.Scatter(x=df["window_start"], y=df["avg_price"], mode="lines", line=dict(color=color, width=2.5, shape="spline")))
    fig.update_layout(
        height=50,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


st.title("Crypto Market: Real-Time Price & Volume")
st.caption("Live trade data streamed from Binance, aggregated into 1-minute windows by Spark.")


@st.fragment(run_every=f"{REFRESH_SECONDS}s")
def render():
    metrics = load(
        """
        select window_start, window_end, symbol, avg_price, min_price, max_price, total_volume, trade_count
        from price_metrics_1m
        order by window_start
        """
    )
    if metrics.empty:
        st.info("No aggregated windows yet. The first 1-minute window lands here shortly after the pipeline starts.")
        return

    symbols = [s for s in COIN_STYLE if s in metrics["symbol"].unique()]
    st.session_state.setdefault("selected_symbol", symbols[0])

    # ---- the card grid: every coin, five per row ----
    for row_start in range(0, len(symbols), CARDS_PER_ROW):
        row_symbols = symbols[row_start : row_start + CARDS_PER_ROW]
        cols = st.columns(CARDS_PER_ROW)
        for c, sym in zip(cols, row_symbols):
            style = COIN_STYLE[sym]
            coin_df = metrics[metrics["symbol"] == sym].sort_values("window_start")
            latest_row = coin_df.iloc[-1]
            first_p, last_p = coin_df["avg_price"].iloc[0], coin_df["avg_price"].iloc[-1]
            pct = (last_p - first_p) / first_p * 100 if first_p else 0
            trend = UP if pct >= 0 else DOWN
            with c:
                with st.container(border=True):
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:6px;">'
                        f'<span style="width:8px;height:8px;border-radius:50%;background:{style["color"]};display:inline-block;"></span>'
                        f'<span style="color:#9298a8;font-weight:600;font-size:0.82rem;letter-spacing:0.02em;">{sym}</span></div>'
                        f'<div style="font-size:1.2rem;font-weight:700;color:#f2f2f5;margin:6px 0 2px;white-space:nowrap;">${latest_row["avg_price"]:,.2f}</div>'
                        f'<div style="font-size:0.78rem;font-weight:600;color:{trend};margin-bottom:6px;">{"+" if pct >= 0 else ""}{pct:.2f}%</div>',
                        unsafe_allow_html=True,
                    )
                    st.plotly_chart(sparkline(coin_df, trend), use_container_width=True, config={"displayModeBar": False})
                    if st.button("View details", key=f"select_{sym}", use_container_width=True):
                        st.session_state.selected_symbol = sym

    # ---- the detail panel: everything about just the selected coin ----
    sel = st.session_state.selected_symbol
    style = COIN_STYLE[sel]
    sel_df = metrics[metrics["symbol"] == sel].sort_values("window_start")
    first_price = sel_df.iloc[0]["avg_price"]
    last_price = sel_df.iloc[-1]["avg_price"]
    pct_change = (last_price - first_price) / first_price * 100 if first_price else 0

    trend = UP if pct_change >= 0 else DOWN
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        header_col, stat1, stat2, stat3, stat4 = st.columns([2.2, 1, 1, 1, 1])
        with header_col:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;">'
                f'<span style="width:10px;height:10px;border-radius:50%;background:{style["color"]};display:inline-block;"></span>'
                f'<span style="color:#9298a8;font-size:1.05rem;font-weight:600;">{style["label"]} ({sel})</span></div>'
                f'<div style="font-size:2.2rem;font-weight:800;color:#f8f8fa;margin-top:4px;">${last_price:,.2f}'
                f'<span style="font-size:1.1rem;font-weight:600;color:{trend};margin-left:10px;">'
                f'{"+" if pct_change >= 0 else ""}{pct_change:.2f}%</span></div>',
                unsafe_allow_html=True,
            )

        # Plain markdown instead of st.metric: st.metric silently truncates
        # its value with an ellipsis once the column gets narrow, which a
        # 4-stats-in-a-row layout runs into constantly. A smaller,
        # unbounded font avoids that entirely.
        def stat_block(col, label, value):
            col.markdown(
                f'<div style="color:#8a8fa3;font-size:0.8rem;">{label}</div>'
                f'<div style="color:#f2f2f5;font-size:1.15rem;font-weight:700;white-space:nowrap;">{value}</div>',
                unsafe_allow_html=True,
            )

        decimals = 2 if sel_df["max_price"].max() < 100 else 0
        stat_block(stat1, "High", f"${sel_df['max_price'].max():,.{decimals}f}")
        stat_block(stat2, "Low", f"${sel_df['min_price'].min():,.{decimals}f}")
        stat_block(stat3, "Volume", f"{sel_df['total_volume'].sum():,.2f}")
        stat_block(stat4, "Trades", f"{int(sel_df['trade_count'].sum()):,}")

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.subheader("Price")
            # No fill-to-zero here on purpose: a price series that never
            # gets near zero (BTC at $75k, say) would render as a flat
            # line hugging the top of the chart if the axis were forced
            # to start at 0. A tight range around the data's own min/max
            # shows the actual movement instead.
            price_min, price_max = sel_df["avg_price"].min(), sel_df["avg_price"].max()
            pad = max((price_max - price_min) * 0.15, price_max * 0.001)
            price_fig = go.Figure(
                go.Scatter(
                    x=sel_df["window_start"],
                    y=sel_df["avg_price"],
                    mode="lines",
                    line=dict(color=trend, width=2.5, shape="spline", smoothing=0.4),
                    fill="tozeroy",
                    fillcolor=trend + "14",
                )
            )
            price_fig.update_layout(
                height=320,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c9c9d1"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.06)", range=[price_min - pad, price_max + pad]),
            )
            st.plotly_chart(price_fig, use_container_width=True, config={"displayModeBar": False})

        with chart_col2:
            st.subheader("Volume per minute")
            vol_fig = go.Figure(go.Bar(x=sel_df["window_start"], y=sel_df["total_volume"], marker_color=trend, marker_line_width=0))
            vol_fig.update_layout(
                height=320,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c9c9d1"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                bargap=0.25,
            )
            st.plotly_chart(vol_fig, use_container_width=True, config={"displayModeBar": False})

        st.subheader(f"Recent {sel} trades")
        recent_trades = load(
            """
            select event_time, price, quantity, is_buyer_maker
            from raw_trades
            where symbol = %(symbol)s
            order by event_time desc
            limit 200
            """,
            params={"symbol": sel},
        )
        st.dataframe(recent_trades, use_container_width=True, height=250)


render()
