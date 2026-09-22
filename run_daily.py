from scanner import get_combined_watchlist
from trader import PaperTrader

def main():
    print("=== Starting Daily Trading Bot ===")
    
    # שליפת 15 מניות מומנטום + 5 מניות Quiver/בעלי עניין (סה"כ 20 מניות)
    watchlist = get_combined_watchlist(momentum_n=15, insider_n=5)
    
    # אתחול הטריידר והרצה
    trader = PaperTrader()
    trader.send_portfolio_summary_alert()
    trader.run_daily_scan(watchlist=watchlist)
    
    print("=== Daily Run Complete ===")

if __name__ == '__main__':
    main()