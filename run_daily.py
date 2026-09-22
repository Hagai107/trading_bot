from scanner import update_hottest_watchlist
from trader import PaperTrader

def main():
    print("=== Starting Daily Trading Bot ===")
    
    # 1. הפעלת הסורק ומציאת 10 המניות החמות של היום
    hottest_stocks = update_hottest_watchlist(top_n=15)
    
    # 2. אתחול הטריידר של אלפקה
    trader = PaperTrader()
    
    # 3. שליחת סטטוס עדכני לטלגרם
    trader.send_portfolio_summary_alert()
    
    # 4. הרצת הלוגיקה והמסחר על המניות שנמצאו
    trader.run_daily_scan(watchlist=hottest_stocks)
    
    print("=== Daily Run Complete ===")

if __name__ == '__main__':
    main()