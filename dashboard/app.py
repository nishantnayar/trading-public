"""Quantis dashboard — basic smoke-test build.

Reads live from the quantis Postgres DB to confirm the data layer is working:
coverage KPIs, universe browser, and per-symbol price/volume charts.

Run:  uv run streamlit run dashboard/app.py
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from quantis.db.engine import get_engine

st.set_page_config(page_title="Quantis", page_icon="📈", layout="wide")

# --- palette (matches the design mockups) ---
TEAL, GREEN, RED, MUTED, PANEL = "#2dd4bf", "#22c55e", "#f43f5e", "#8b97a3", "#12181f"


@st.cache_data(ttl=300)
def load_coverage() -> dict:
    q = """
        SELECT count(*) AS rows,
               count(DISTINCT symbol) AS symbols,
               min(date) AS start, max(date) AS "end"
        FROM daily_bars
    """
    return pd.read_sql(q, get_engine()).iloc[0].to_dict()


@st.cache_data(ttl=300)
def load_universe() -> pd.DataFrame:
    q = """
        SELECT s.symbol, s.name, s.sector,
               count(b.date) AS bars,
               max(b.date) AS last_bar
        FROM symbols s
        LEFT JOIN daily_bars b ON b.symbol = s.symbol
        WHERE s.active
        GROUP BY s.symbol, s.name, s.sector
        ORDER BY s.symbol
    """
    return pd.read_sql(q, get_engine())


@st.cache_data(ttl=300)
def load_bars(symbol: str, start: dt.date) -> pd.DataFrame:
    q = """
        SELECT date, open, high, low, close, volume
        FROM daily_bars
        WHERE symbol = %(symbol)s AND date >= %(start)s
        ORDER BY date
    """
    df = pd.read_sql(q, get_engine(), params={"symbol": symbol, "start": start})
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    return df


def kpi(col, label: str, value: str, color: str = "#e6edf3") -> None:
    col.markdown(
        f"<div style='background:{PANEL};border:1px solid #1e2831;border-radius:12px;"
        f"padding:16px 18px'><div style='color:{MUTED};font-size:12px;text-transform:"
        f"uppercase;letter-spacing:.6px'>{label}</div><div style='font-size:26px;"
        f"font-weight:600;color:{color};margin-top:6px'>{value}</div></div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.markdown(
        "<h2 style='margin-bottom:0'>📈 Quantis</h2>"
        "<div style='color:#5f6b78;font-family:monospace;font-size:13px'>"
        "XS-EQUITY ML · data-layer smoke test</div>",
        unsafe_allow_html=True,
    )

    try:
        cov = load_coverage()
        uni = load_universe()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Database not reachable: {exc}")
        st.info("Check .env (PGPASSWORD) and that Postgres + the `quantis` DB exist.")
        return

    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "Daily bars", f"{int(cov['rows']):,}", TEAL)
    kpi(c2, "Symbols", f"{int(cov['symbols'])}")
    kpi(c3, "History start", str(cov["start"]))
    kpi(c4, "Latest bar", str(cov["end"]))

    st.divider()
    left, right = st.columns([1, 2])

    with left:
        st.subheader("Universe")
        sectors = ["All"] + sorted(uni["sector"].dropna().unique().tolist())
        sector = st.selectbox("Sector", sectors)
        view = uni if sector == "All" else uni[uni["sector"] == sector]
        st.caption(f"{len(view)} names")
        st.dataframe(
            view[["symbol", "sector", "bars", "last_bar"]],
            hide_index=True,
            use_container_width=True,
            height=380,
        )

    with right:
        st.subheader("Price & volume")
        symbols = view["symbol"].tolist() or uni["symbol"].tolist()
        default = "AAPL" if "AAPL" in symbols else symbols[0]
        sym = st.selectbox("Symbol", symbols, index=symbols.index(default))
        lookback = st.slider("Lookback (years)", 1, 9, 3)
        start = dt.date.today() - dt.timedelta(days=365 * lookback)

        bars = load_bars(sym, start)
        if bars.empty:
            st.warning(f"No bars for {sym} in range.")
        else:
            last, first = bars["close"].iloc[-1], bars["close"].iloc[0]
            chg = (last / first - 1) * 100
            m1, m2, m3 = st.columns(3)
            kpi(m1, "Last close", f"${last:,.2f}")
            kpi(m2, f"{lookback}y change", f"{chg:+.1f}%", GREEN if chg >= 0 else RED)
            kpi(m3, "Bars", f"{len(bars):,}")

            fig = go.Figure(
                go.Candlestick(
                    x=bars["date"], open=bars["open"], high=bars["high"],
                    low=bars["low"], close=bars["close"],
                    increasing_line_color=GREEN, decreasing_line_color=RED, name=sym,
                )
            )
            fig.update_layout(
                template="plotly_dark", height=420, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis_rangeslider_visible=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            vol = go.Figure(go.Bar(x=bars["date"], y=bars["volume"], marker_color=TEAL))
            vol.update_layout(
                template="plotly_dark", height=140, margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title=None, xaxis_title=None,
            )
            st.plotly_chart(vol, use_container_width=True)
            st.caption("Volume is IEX-feed only (free tier) — understated vs full market.")


if __name__ == "__main__":
    main()
