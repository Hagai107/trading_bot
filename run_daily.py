from scanner import update_hottest_watchlist
from trader import PaperTrader

def main():
    # 1. סריקה בלייב של השוק ועדכון ה-DB ב-10 המניות החמות של היום
    watchlist = update_hottest_watchlist(top_n=10)
    
    # 2. הרצת אסטרטגיית המסחר היומית על רשימת 10 החמות
    trader = PaperTrader()
    trader.run_daily_scan(watchlist)

if __name__ == "__main__":
    main()