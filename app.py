import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

from database import init_db, get_setting, set_setting
from trader import PaperTrader
from backtest import run_comprehensive_backtest

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="ApexAlgo | Trading Terminal",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

init_db()
trader = PaperTrader()

# --- CUSTOM MODERN LIGHT THEME CSS ---
st.markdown("""
<style>
    /* Light Theme Core */
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Hide Streamlit Header & Footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Modern Light Cards (Metrics) */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #CBD5E1;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
        transform: translateY(-2px);
    }
    div[data-testid="stMetricLabel"] {
        color: #64748B;
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetricValue"] {
        color: #0F172A;
        font-weight: 700;
        font-size: 1.65rem;
    }

    /* Modern Blue Gradient Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: #FFFFFF;
        border: none;
        padding: 0.65rem 1.2rem;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
        transition: all 0.2s ease-in-out;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.35);
        transform: translateY(-1px);
        color: #FFFFFF;
    }

    /* Clean Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    
    /* Tabs Navigation */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        padding: 4px 0px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        background-color: #FFFFFF;
        border-radius: 8px;
        color: #64748B;
        border: 1px solid #E2E8F0;
        padding: 0 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #EFF6FF !important;
        color: #2563EB !important;
        border-color: #BFDBFE !important;
    }

    /* Form Container Borders */
    div[data-testid="stForm"] {
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        background-color: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: RISK MANAGEMENT & PARAMETERS ---
with st.sidebar:
    st.markdown("## ⚡ **ApexAlgo Controls**")
    st.caption("Quantitative Risk & Strategy Settings")
    st.markdown("---")

    cash_val = st.number_input("Initial Cash Balance ($)", value=float(get_setting('cash', 10000.0)), step=500.0)
    pos_size = st.slider("Position Size (% Portfolio)", min_value=1, max_value=20, value=int(get_setting('pos_size_pct', 5)))
    max_daily_loss = st.slider("Max Daily Loss Limit (%)", min_value=1, max_value=10, value=int(get_setting('max_daily_loss_pct', 2)))
    max_positions = st.number_input("Max Concurrent Positions", min_value=1, max_value=10, value=int(get_setting('max_positions', 3)))
    
    col_sl, col_tp = st.columns(2)
    stop_loss_pct = col_sl.number_input("Stop-Loss (%)", min_value=1.0, max_value=10.0, value=float(get_setting('stop_loss_pct', 3.0)), step=0.5)
    take_profit_pct = col_tp.number_input("Take-Profit (%)", min_value=1.0, max_value=25.0, value=float(get_setting('take_profit_pct', 8.0)), step=0.5)

    st.markdown("---")
    
    default_watchlist = "NVDA, AAPL, MSFT, TSLA, AMD, GOOGL"
    saved_watchlist = str(get_setting('watchlist', default_watchlist))

    watch_input = st.text_area("Watchlist Tickers", value=saved_watchlist, help="Comma-separated ticker symbols")
    watch_list = [s.strip().upper() for s in watch_input.split(",") if s.strip()]

    if st.button("💾 Save Configuration", use_container_width=True):
        set_setting('cash', cash_val)
        set_setting('pos_size_pct', pos_size)
        set_setting('max_daily_loss_pct', max_daily_loss)
        set_setting('max_positions', max_positions)
        set_setting('stop_loss_pct', stop_loss_pct)
        set_setting('take_profit_pct', take_profit_pct)
        set_setting('watchlist', watch_input)
        st.sidebar.success("Configuration saved to SQLite!")

# --- MAIN NAVIGATION TABS ---
tab_main, tab_backtest, tab_db = st.tabs(["📊 Live Dashboard", "🧪 Backtesting Engine", "🗄️ SQLite Database"])

# ==================== TAB 1: DASHBOARD ====================
with tab_main:
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.title("📈 Execution Dashboard")
        st.caption("Automated Swing Trading & Portfolio Management System")
    with col_head2:
        st.write(" ")
        if st.button("🚀 Run Daily Scan", use_container_width=True):
            with st.spinner("Analyzing market indicators..."):
                res_msg = trader.run_daily_scan(watch_list)
                st.toast(res_msg, icon="✅")

    st.markdown("---")

    # KPIs
    total_val, cash, pos_val = trader.get_portfolio_summary()
    
    conn = sqlite3.connect("portfolio.db")
    df_trades = pd.read_sql("SELECT * FROM trades_history WHERE action='SELL'", conn)
    conn.close()

    if not df_trades.empty:
        wins = len(df_trades[df_trades['pnl'] > 0])
        win_rate = (wins / len(df_trades)) * 100
        win_rate_str = f"{win_rate:.1f}%"
    else:
        win_rate_str = "N/A"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Portfolio Value", f"${total_val:,.2f}")
    c2.metric("Available Cash", f"${cash:,.2f}")
    c3.metric("Open Positions Value", f"${pos_val:,.2f}")
    c4.metric("Realized Win Rate", win_rate_str)

    st.markdown("---")

    # Visuals Row
    col_left, col_right = st.columns([3, 2])

    with col_left:
        with st.container(border=True):
            st.subheader("📈 Portfolio Equity Curve")
            conn = sqlite3.connect("portfolio.db")
            df_hist = pd.read_sql("SELECT * FROM portfolio_history ORDER BY date ASC", conn)
            conn.close()

            if not df_hist.empty:
                fig = px.area(df_hist, x='date', y='total_value')
                fig.update_traces(
                    line_color="#2563EB", 
                    fillcolor="rgba(37, 99, 235, 0.08)",
                    line_width=2.5
                )
                fig.update_layout(
                    template="plotly_white",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#64748B"),
                    margin=dict(l=10, r=10, t=20, b=10),
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#F1F5F9", tickprefix="$")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No execution history recorded yet. Click 'Run Daily Scan' to start tracking.")

    with col_right:
        with st.container(border=True):
            st.subheader("📌 Open Positions")
            conn = sqlite3.connect("portfolio.db")
            df_pos = pd.read_sql("SELECT symbol, shares, entry_price, current_price, stop_loss, take_profit FROM positions", conn)
            conn.close()

            if not df_pos.empty:
                st.dataframe(
                    df_pos,
                    column_config={
                        "symbol": "Ticker",
                        "shares": st.column_config.NumberColumn("Shares", format="%.2f"),
                        "entry_price": st.column_config.NumberColumn("Entry ($)", format="$%.2f"),
                        "current_price": st.column_config.NumberColumn("Current ($)", format="$%.2f"),
                        "stop_loss": st.column_config.NumberColumn("Stop Loss ($)", format="$%.2f"),
                        "take_profit": st.column_config.NumberColumn("Take Profit ($)", format="$%.2f"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.caption("No active market positions in portfolio.")

# ==================== TAB 2: BACKTESTING ====================
with tab_backtest:
    st.title("🧪 Quantitative Strategy Backtester")
    st.caption("Validate trading logic against historical market data prior to live deployment.")

    with st.container(border=True):
        col_bt1, col_bt2, col_bt3 = st.columns(3)
        
        bt_symbol = col_bt1.text_input(
            "Ticker Symbol", 
            value="QQQ",
            help="The stock or ETF ticker symbol to test (e.g., QQQ, SPY, NVDA)."
        )
        start_date = col_bt2.date_input(
            "Start Date", 
            value=pd.to_datetime("2022-01-01"),
            help="Beginning date of the historical backtesting period."
        )
        end_date = col_bt3.date_input(
            "End Date", 
            value=pd.to_datetime("2026-09-01"),
            help="Ending date of the historical backtesting period."
        )

        run_bt = st.button(
            "▶️ Execute Backtest Simulation", 
            use_container_width=True,
            help="Click to fetch historical price data and compute technical strategy performance."
        )

    if run_bt:
        with st.spinner(f"Running simulation on {bt_symbol}..."):
            results = run_comprehensive_backtest(bt_symbol, str(start_date), str(end_date))
            
            # שליפת מחיר המניה העדכני בזמן אמת מ-yfinance
            try:
                ticker_info = yf.Ticker(bt_symbol)
                current_price = ticker_info.fast_info['lastPrice']
                price_display = f"${current_price:,.2f}"
            except Exception:
                current_price = results.get('current_price', None)
                price_display = f"${current_price:,.2f}" if current_price else "N/A"

        if results:
            st.markdown(f"### Performance Summary: **{bt_symbol}**")
            
            # 6 עמודות KPI - כולל מחיר המניה הנוכחי
            m0, m1, m2, m3, m4, m5 = st.columns(6)
            m0.metric(
                "Current Price",
                price_display,
                help="The latest market price for the selected ticker symbol."
            )
            m1.metric(
                "Win Rate", 
                f"{results['win_rate']}%", 
                help="Target: >45%\n\nPercentage of completed trades that ended with a positive profit."
            )
            m2.metric(
                "Risk / Reward", 
                f"1:{results['risk_reward']}", 
                help="Target: >= 1:1.5\n\nRatio of average winning trade profit relative to average losing trade loss."
            )
            m3.metric(
                "Sharpe Ratio", 
                f"{results['sharpe_ratio']}", 
                help="Target: > 1.0\n\nAnnualized risk-adjusted return metric measuring excess return per unit of volatility."
            )
            m4.metric(
                "Max Drawdown", 
                f"{results['max_drawdown']}%", 
                help="Target: < 20%\n\nThe maximum percentage decline from peak equity to lowest trough during the simulation."
            )
            m5.metric(
                "Total Trades", 
                f"{results['total_trades']}", 
                help="Target: >= 100 trades\n\nNumber of trades executed during the period. Requires >=100 for statistical validity."
            )

            col_chk, col_chart = st.columns([1, 2])

            with col_chk:
                with st.container(border=True):
                    st.markdown("#### **Strategy Criteria**")
                    st.caption("Hover over any item for parameter details:")
                    
                    CRITERIA_EXPLANATIONS = {
                        "Win Rate (>45%)": "Win Rate (>45%): Percentage of winning trades out of total closed positions. Ensures the strategy doesn't rely solely on rare outlier trades.",
                        "Risk/Reward (>= 1:1.5)": "Risk/Reward (>= 1:1.5): Ratio of average profit on winning trades vs average loss on losing trades. 1:1.5 ensures gains outweigh losses.",
                        "Sharpe Ratio (>1.0)": "Sharpe Ratio (>1.0): Risk-adjusted performance relative to volatility. Values above 1.0 indicate strong performance per unit of risk.",
                        "Max Drawdown (<20%)": "Max Drawdown (<20%): Largest peak-to-trough decline in account value. Measures drawdown risk during unfavorable market trends.",
                        "Min Sample Size (>=100 trades)": "Min Sample Size (>=100 trades): Total trades evaluated. Requires at least 100 trades for statistical confidence and curve-fitting prevention."
                    }

                    for check_name, passed in results['checks'].items():
                        tooltip_text = CRITERIA_EXPLANATIONS.get(check_name, check_name)
                        badge_bg = "#F0FDF4" if passed else "#FEF2F2"
                        badge_color = "#166534" if passed else "#991B1B"
                        border_color = "#BBF7D0" if passed else "#FECACA"
                        icon = "✔️" if passed else "❌"
                        
                        st.markdown(f"""
                        <div title="{tooltip_text}" style="
                            background-color: {badge_bg};
                            color: {badge_color};
                            border: 1px solid {border_color};
                            padding: 10px 14px;
                            border-radius: 8px;
                            margin-bottom: 8px;
                            font-weight: 600;
                            cursor: help;
                            display: flex;
                            align-items: center;
                            justify-content: space-between;
                            font-size: 0.88rem;
                            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
                        ">
                            <div>
                                <span style="margin-right: 6px;">{icon}</span>
                                <span>{check_name}</span>
                            </div>
                            <span style="opacity: 0.5; font-size: 0.75rem;">ℹ️</span>
                        </div>
                        """, unsafe_allow_html=True)

            with col_chart:
                with st.container(border=True):
                    fig_bt = px.line(results['equity_curve'], title=f"Historical Equity Growth - {bt_symbol}")
                    fig_bt.update_traces(line_color="#2563EB", line_width=2)
                    fig_bt.update_layout(
                        template="plotly_white",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#64748B"),
                        margin=dict(l=10, r=10, t=30, b=10),
                        yaxis=dict(tickprefix="$", gridcolor="#F1F5F9")
                    )
                    st.plotly_chart(fig_bt, use_container_width=True)
        else:
            st.error("Failed to retrieve historical data for the selected ticker/date range.")

# ==================== TAB 3: DATABASE INSPECTOR ====================
with tab_db:
    st.title("🗄️ Live SQLite Database Inspector")
    st.caption("Direct read access to local `portfolio.db` tables.")

    conn = sqlite3.connect("portfolio.db")

    col_db1, col_db2 = st.columns(2)

    with col_db1:
        with st.container(border=True):
            st.subheader("1. Active Positions (`positions`)")
            st.dataframe(pd.read_sql("SELECT * FROM positions", conn), use_container_width=True, hide_index=True)

        with st.container(border=True):
            st.subheader("3. System Settings (`settings`)")
            st.dataframe(pd.read_sql("SELECT * FROM settings", conn), use_container_width=True, hide_index=True)

    with col_db2:
        with st.container(border=True):
            st.subheader("2. Trade Execution History (`trades_history`)")
            st.dataframe(pd.read_sql("SELECT * FROM trades_history ORDER BY timestamp DESC", conn), use_container_width=True, hide_index=True)

        with st.container(border=True):
            st.subheader("4. Portfolio History (`portfolio_history`)")
            st.dataframe(pd.read_sql("SELECT * FROM portfolio_history ORDER BY date DESC", conn), use_container_width=True, hide_index=True)

    conn.close()