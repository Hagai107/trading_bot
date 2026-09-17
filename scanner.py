import sqlite3
import pandas as pd
import yfinance as yf

def fetch_live_market_tickers():
    """שליפה דינמית מ-Wikipedia של מניות מדדי S&P 500 ו-NASDAQ 100"""
    tickers = set()
    
    # 1. שליפת מניות S&P 500
    try:
        url_sp500 = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url_sp500)
        sp500_tickers = tables[0]['Symbol'].tolist()
        tickers.update(sp500_tickers)
        print(f"🌐 Fetched {len(sp500_tickers)} tickers from S&P 500.")
    except Exception as e:
        print(f"⚠️ Failed to fetch S&P 500 tickers: {e}")

    # 2. שליפת מניות NASDAQ 100
    try:
        url_nasdaq = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        tables = pd.read_html(url_nasdaq)
        for table in tables:
            if 'Ticker' in table.columns:
                nasdaq_tickers = table['Ticker'].tolist()
                tickers.update(nasdaq_tickers)
                print(f"🌐 Fetched {len(nasdaq_tickers)} tickers from NASDAQ 100.")
                break
    except Exception as e:
        print(f"⚠️ Failed to fetch NASDAQ 100 tickers: {e}")

    cleaned_tickers = [t.replace('.', '-') for t in tickers if isinstance(t, str)]
    return cleaned_tickers


def update_hottest_watchlist(top_n=10):
    print("🔥 Starting dynamic live market scan...")
    
    candidate_pool = fetch_live_market_tickers()
    
    if not candidate_pool:
        print("⚠️ Fallback to emergency ticker list.")
        candidate_pool = ["AAPL", "NVDA", "TSLA", "AMD", "AMZN", "MSFT", "GOOGL", "META", "PLTR"]

    try:
        print(f"⚡ Analyzing {len(candidate_pool)} live market tickers simultaneously...")
        
        # ניתוח מרוכז ומהיר במיקוד מרובה תהליכים (Multi-threading)
        data = yf.download(candidate_pool, period="5d", interval="1d", threads=True, progress=False)
        close_prices = data['Close']
        
        # חישוב אחוז שינוי ב-3 ימים האחרונים
        momentum = ((close_prices.iloc[-1] - close_prices.iloc[-3]) / close_prices.iloc[-3]) * 100
        
        # בחירת 10 המניות המובילות בלבד
        hottest_tickers = momentum.dropna().sort_values(ascending=False).head(top_n).index.tolist()
        
        print(f"✨ Top {top_n} Hottest Market Tickers Selected: {hottest_tickers}")
        
        # דריסת ה-Watchlist ב-DB ועדכון ל-10 החמות של היום בלבד
        conn = sqlite3.connect("portfolio.db")
        cursor = conn.cursor()
        watchlist_str = ",".join(hottest_tickers)
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('watchlist', ?)", (watchlist_str,))
        conn.commit()
        conn.close()
        
        return hottest_tickers
        
    except Exception as e:
        print(f"❌ Error during bulk analysis: {e}")
        return candidate_pool[:top_n]