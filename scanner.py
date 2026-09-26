import io
import pandas as pd
import requests
import yfinance as yf

def fetch_live_market_tickers():
    """שליפה דינמית מ-Wikipedia של S&P 500, NASDAQ 100, S&P MidCap 400 ו-S&P SmallCap 600"""
    tickers = set()
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    }

    # 1. S&P 500 (חברות ענק)
    try:
        url_sp500 = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url_sp500, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        tickers.update(tables[0]['Symbol'].tolist())
    except Exception as e:
        print(f'⚠️ Failed to fetch S&P 500 tickers: {e}')

    # 2. NASDAQ 100 (טכנולוגיה וצמיחה)
    try:
        url_nasdaq = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        response = requests.get(url_nasdaq, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        for table in tables:
            if 'Ticker' in table.columns:
                tickers.update(table['Ticker'].tolist())
                break
    except Exception as e:
        print(f'⚠️ Failed to fetch NASDAQ 100 tickers: {e}')

    # 3. S&P MidCap 400 (חברות בינוניות - מניות צמיחה מעולות)
    try:
        url_sp400 = 'https://en.wikipedia.org/wiki/List_of_S%26P_400_companies'
        response = requests.get(url_sp400, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        for table in tables:
            cols = table.columns
            if 'Ticker symbol' in cols:
                tickers.update(table['Ticker symbol'].tolist())
                break
            elif 'Symbol' in cols:
                tickers.update(table['Symbol'].tolist())
                break
    except Exception as e:
        print(f'⚠️ Failed to fetch S&P 400 tickers: {e}')

    # 4. S&P SmallCap 600 (חברות קטנות)
    try:
        url_sp600 = 'https://en.wikipedia.org/wiki/List_of_S%26P_600_companies'
        response = requests.get(url_sp600, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        for table in tables:
            cols = table.columns
            if 'Ticker symbol' in cols:
                tickers.update(table['Ticker symbol'].tolist())
                break
            elif 'Symbol' in cols:
                tickers.update(table['Symbol'].tolist())
                break
    except Exception as e:
        print(f'⚠️ Failed to fetch S&P 600 tickers: {e}')

    clean_tickers = [
        str(t).replace('.', '-').strip() 
        for t in tickers 
        if isinstance(t, str) and len(str(t).strip()) <= 5
    ]
    print(f'🌐 Total unique market tickers collected: {len(clean_tickers)}')
    return clean_tickers


def fetch_insider_tickers(top_n=5):
    """שליפת מניות עם קניות חזקות של בעלי עניין (חינמי ללא API Key)"""
    print(f'\n🏛️ Fetching Top {top_n} Insider Buying Tickers...')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        url = "http://openinsider.com/item?s=&o=&pl=&ph=&ll=&lh=&fd=30&fdr=&td=0&tdr=&fdxc=1&tx=P&tdxc=1"
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        
        if len(tables) > 2:
            insider_df = tables[2]
            if 'Ticker' in insider_df.columns:
                raw_tickers = insider_df['Ticker'].dropna().unique()
                insider_tickers = [
                    str(t).strip() for t in raw_tickers 
                    if len(str(t).strip()) <= 5 and str(t).strip().isalpha()
                ][:top_n]
                
                if insider_tickers:
                    print(f'✅ Fetched Insider Buys: {insider_tickers}')
                    return insider_tickers

    except Exception as e:
        print(f'⚠️ Failed to fetch Insider data: {e}')

    fallback_insiders = ['PLTR', 'NVDA', 'AMZN', 'META', 'PANW']
    print(f'ℹ️ Using Insider Fallback List: {fallback_insiders[:top_n]}')
    return fallback_insiders[:top_n]


def get_combined_watchlist(momentum_n=15, insider_n=5):
    """שילוב 15 מניות מומנטום + 5 מניות בעלי עניין לרשימה של 20 מניות"""
    print('\n🔥 Starting dual-strategy market scan...')

    # 1. מציאת 15 מניות מומנטום מתוך מאגר של ~1500 מניות
    candidate_pool = fetch_live_market_tickers()
    momentum_tickers = []

    if candidate_pool:
        try:
            print(f'⚡ Analyzing momentum for {len(candidate_pool)} market tickers...')
            data = yf.download(candidate_pool, period='5d', interval='1d', threads=True, progress=False)
            close_prices = data['Close']
            momentum = ((close_prices.iloc[-1] - close_prices.iloc[-3]) / close_prices.iloc[-3]) * 100
            momentum_tickers = momentum.dropna().sort_values(ascending=False).head(momentum_n).index.tolist()
        except Exception as e:
            print(f'❌ Error during momentum analysis: {e}')

    if not momentum_tickers:
        momentum_tickers = ['AAPL', 'NVDA', 'TSLA', 'AMD', 'AMZN', 'MSFT', 'GOOGL', 'META', 'PLTR', 'NFLX', 'INTC', 'QCOM', 'BAC', 'JPM', 'DIS'][:momentum_n]

    # 2. מציאת 5 מניות בעלי עניין
    insider_list = fetch_insider_tickers(top_n=insider_n)

    # 3. איחוד ללא כפילויות
    combined_list = []
    for ticker in momentum_tickers + insider_list:
        if ticker not in combined_list:
            combined_list.append(ticker)

    print(f'\n✨ Final Combined Watchlist ({len(combined_list)} Tickers): {combined_list}')
    return combined_list
