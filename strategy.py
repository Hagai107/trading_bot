import yfinance as yf
import pandas as pd
import numpy as np

def filter_volume(symbol, min_avg_volume=500000):
    """Filters stocks by average daily trading volume (>500K shares threshold)."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")
        if hist.empty:
            return False
        avg_vol = hist['Volume'].mean()
        return avg_vol >= min_avg_volume
    except Exception:
        return False

def analyze_stock(symbol):
    """
    Analyzes a stock using Gap Up, Volume, Moving Averages, and RSI.
    """
    df = yf.download(symbol, period="3mo", interval="1d", progress=False)
    if df.empty or len(df) < 50:
        return "HOLD", 0.0, "Insufficient data"

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']
    open_price = df['Open']
    volume = df['Volume']

    current_price = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    today_open = float(open_price.iloc[-1])
    
    gap_pct = ((today_open - prev_close) / prev_close) * 100
    
    avg_vol_30 = volume.rolling(30).mean().iloc[-1]
    vol_ratio = (volume.iloc[-1] / avg_vol_30) if avg_vol_30 > 0 else 1.0

    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]

    # --- BUY Condition 1: Gap Up + Momentum ---
    if (gap_pct >= 4.0) and (vol_ratio >= 1.5) and (sma20 > sma50) and (rsi < 70):
        return "BUY", current_price, f"Gap Up strategy (+{gap_pct:.1f}%, Vol ratio {vol_ratio:.1f}x)"

    # --- BUY Condition 2: Moving Average Crossover ---
    if (sma20 > sma50) and (close.iloc[-2] <= sma20) and (current_price > sma20) and (rsi < 65):
        return "BUY", current_price, "MA Crossover (MA20 > MA50)"

    # --- SELL Conditions ---
    if (rsi > 75) or (current_price < sma20):
        return "SELL", current_price, "MA20 breakdown or RSI Overbought"

    return "HOLD", current_price, "No signal"