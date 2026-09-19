import io
import pandas as pd
import requests
import yfinance as yf

def fetch_live_market_tickers():
    """שליפה דינמית מ-Wikipedia של מניות מדדי S&P 500 ו-NASDAQ 100 עם זיהוי דפדפן"""
    tickers = set()

    # הגדרת User-Agent כדי למנוע חסימת HTTP 403 מצד ויקיפדיה
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    }

    # 1. שליפת מניות S&P 500
    try:
        url_sp500 = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        response = requests.get(url_sp500, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        sp500_tickers = tables[0]['Symbol'].tolist()
        tickers.update(sp500_tickers)
        print(f'🌐 Fetched {len(sp500_tickers)} tickers from S&P 500.')
    except Exception as e:
        print(f'⚠️ Failed to fetch S&P 500 tickers: {e}')

    # 2. שליפת מניות NASDAQ 100
    try:
        url_nasdaq = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        response = requests.get(url_nasdaq, headers=headers, timeout=10)
        tables = pd.read_html(io.StringIO(response.text))
        for table in tables:
            if 'Ticker' in table.columns:
                nasdaq_tickers = table['Ticker'].tolist()
                tickers.update(nasdaq_tickers)
                print(f'🌐 Fetched {len(nasdaq_tickers)} tickers from NASDAQ 100.')
                break
    except Exception as e:
        print(f'⚠️ Failed to fetch NASDAQ 100 tickers: {e}')

    cleaned_tickers = [
        t.replace('.', '-') for t in tickers if isinstance(t, str)
    ]
    return cleaned_tickers


def update_hottest_watchlist(top_n=10):
    print('\n🔥 Starting dynamic live market scan...')

    candidate_pool = fetch_live_market_tickers()

    if not candidate_pool:
        print('⚠️ Fallback to emergency ticker list.')
        candidate_pool = [
            'AAPL', 'NVDA', 'TSLA', 'AMD', 'AMZN',
            'MSFT', 'GOOGL', 'META', 'PLTR',
        ]

    try:
        print(f'⚡ Analyzing {len(candidate_pool)} live market tickers simultaneously...')

        data = yf.download(
            candidate_pool,
            period='5d',
            interval='1d',
            threads=True,
            progress=False,
        )
        close_prices = data['Close']

        # חישוב מומנטום
        momentum = (
            (close_prices.iloc[-1] - close_prices.iloc[-3]) / close_prices.iloc[-3]
        ) * 100

        hottest_tickers = (
            momentum.dropna().sort_values(ascending=False).head(top_n).index.tolist()
        )

        print(f'✨ Top {top_n} Hottest Market Tickers Selected: {hottest_tickers}')
        return hottest_tickers

    except Exception as e:
        print(f'❌ Error during bulk analysis: {e}')
        return candidate_pool[:top_n]