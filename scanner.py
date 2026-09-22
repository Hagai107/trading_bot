import io
import os
import pandas as pd
import requests
import yfinance as yf

def fetch_live_market_tickers():
    """שליפה דינמית מ-Wikipedia של מניות מדדי S&P 500 ו-NASDAQ 100"""
    tickers = set()
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    }

    try:
        url_sp500 = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url_sp500, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        tickers.update(tables[0]['Symbol'].tolist())
    except Exception as e:
        print(f'⚠️ Failed to fetch S&P 500 tickers: {e}')

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

    return [t.replace('.', '-') for t in tickers if isinstance(t, str)]


def fetch_quiver_insider_tickers(top_n=5):
    """שליפת מניות עם קניות חזקות של בעלי עניין / חברי קונגרס (Quiver Quant / Insider Data)"""
    print(f'\n🏛️ Fetching Top {top_n} Insider/Congress Buying Tickers...')
    
    quiver_api_key = os.getenv('QUIVER_API_KEY')
    headers = {'Authorization': f'Token {quiver_api_key}'} if quiver_api_key else {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    try:
        # אם הוגדר מפתח API של Quiver Quant
        if quiver_api_key:
            url = "https://api.quiverquant.com/beta/live/insiders"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                df = pd.DataFrame(data)
                insider_tickers = df['Ticker'].unique().tolist()[:top_n]
                print(f'✅ Fetched from Quiver API: {insider_tickers}')
                return insider_tickers

        # פתרון סריקה ציבורי/חלופי לדיווחי קניות בעלי עניין
        url = "http://openinsider.com/item?s=&o=&pl=&ph=&ll=&lh=&fd=30&fdr=&td=0&tdr=&fdxc=1&tx=P&tdxc=1"
        tables = pd.read_html(url)
        if len(tables) > 2:
            insider_df = tables[2]
            if 'Ticker' in insider_df.columns:
                insider_tickers = [t for t in insider_df['Ticker'].dropna().unique() if len(t) <= 5][:top_n]
                if insider_tickers:
                    print(f'✅ Fetched Insider Buys: {insider_tickers}')
                    return insider_tickers

    except Exception as e:
        print(f'⚠️ Failed to fetch Insider/Quiver data: {e}')

    # רשימת גיבוי של מניות מובילות בבעלות עניין אם השרת לא זמין
    fallback_insiders = ['PLTR', 'NVDA', 'AMZN', 'META', 'PANW']
    print(f'ℹ️ Using Insider Fallback List: {fallback_insiders[:top_n]}')
    return fallback_insiders[:top_n]


def get_combined_watchlist(momentum_n=15, insider_n=5):
    """שילוב 15 מניות מומנטום + 5 מניות בעלי עניין לרשימה אחת של 20 מניות"""
    print('\n🔥 Starting dual-strategy market scan...')

    # 1. מציאת מניות מומנטום
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

    # 2. מציאת מניות Quiver / בעלי עניין
    insider_tickers = fetch_quiver_insider_tickers(top_n=insider_n)

    # 3. איחוד ללא כפילויות
    combined_list = []
    for ticker in momentum_tickers + insider_tickers:
        if ticker not in combined_list:
            combined_list.append(ticker)

    print(f'\n✨ Final Combined Watchlist ({len(combined_list)} Tickers): {combined_list}')
    return combined_list