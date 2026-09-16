import yfinance as yf
import pandas as pd
import numpy as np

def run_comprehensive_backtest(symbol="SPY", start_date="2022-01-01", end_date="2026-09-01", initial_capital=10000.0):
    df = yf.download(symbol, start=start_date, end=end_date, progress=False)
    if df.empty or len(df) < 100:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    
    df['Signal'] = np.where(df['SMA20'] > df['SMA50'], 1, 0)
    df['Signal'] = df['Signal'].shift(1)

    df['Market_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Signal']
    df['Portfolio_Value'] = initial_capital * (1 + df['Strategy_Return']).cumprod()

    rolling_max = df['Portfolio_Value'].cummax()
    drawdown = (df['Portfolio_Value'] - rolling_max) / rolling_max
    max_drawdown = abs(drawdown.min()) * 100

    daily_returns = df['Strategy_Return'].dropna()
    mean_ret = daily_returns.mean()
    std_ret = daily_returns.std()
    sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252) if std_ret != 0 else 0.0

    trade_entries = df[df['Signal'].diff() == 1]
    trade_exits = df[df['Signal'].diff() == -1]
    
    trade_returns = []
    for entry_date in trade_entries.index:
        subsequent_exits = trade_exits[trade_exits.index > entry_date]
        if not subsequent_exits.empty:
            exit_date = subsequent_exits.index[0]
            ret = (df.loc[exit_date, 'Close'] - df.loc[entry_date, 'Close']) / df.loc[entry_date, 'Close']
            trade_returns.append(ret)

    trade_series = pd.Series(trade_returns)
    winning_trades = trade_series[trade_series > 0]
    losing_trades = trade_series[trade_series < 0]

    total_trades = len(trade_series)
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0.0

    avg_win = winning_trades.mean() if not winning_trades.empty else 0.0
    avg_loss = abs(losing_trades.mean()) if not losing_trades.empty else 1e-9
    risk_reward = avg_win / avg_loss if avg_loss > 0 else 0.0

    checks = {
        "Win Rate (>45%)": win_rate >= 45.0,
        "Risk/Reward (>= 1:1.5)": risk_reward >= 1.5,
        "Sharpe Ratio (>1.0)": sharpe_ratio >= 1.0,
        "Max Drawdown (<20%)": max_drawdown <= 20.0,
        "Min Sample Size (>=100 trades)": total_trades >= 100
    }

    return {
        "symbol": symbol,
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "risk_reward": round(risk_reward, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown": round(max_drawdown, 2),
        "checks": checks,
        "equity_curve": df['Portfolio_Value'],
        "final_value": round(df['Portfolio_Value'].iloc[-1], 2)
    }