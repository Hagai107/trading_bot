from database import init_db, get_setting
from trader import PaperTrader

if __name__ == "__main__":
    init_db()
    
    # טעינת רשימת המעקב מתוך ה-DB (או ברירת מחדל)
    default_watchlist = "NVDA, AAPL, MSFT, TSLA, AMD, GOOGL"
    saved_watchlist = str(get_setting('watchlist', default_watchlist))
    watch_list = [s.strip().upper() for s in saved_watchlist.split(",") if s.strip()]
    
    print(f"🚀 Starting automated daily scan for watchlist: {watch_list}")
    
    trader = PaperTrader()
    result = trader.run_daily_scan(watch_list)
    
    print(f"✅ Result: {result}")