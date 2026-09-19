import os
from trader import PaperTrader

# כאן אתה מייבא את הפונקציה שמביאה את רשימת המניות الحמות מהסורק שלך.
# לדוגמה, אם הקובץ שלך נקרא scraper.py והפונקציה נקראת get_hottest_stocks:
# from scraper import get_hottest_stocks

def main():
    print("🚀 Starting Daily Trading Process with Alpaca...")
    
    # שלב 1: הבאת רשימת המניות לסריקה
    try:
        # תחליף את השורה הבאה בפונקציית הסורק האמיתית שלך:
        # watchlist = get_hottest_stocks()
        
        # רשימה זמנית רק כדי שהקוד ירוץ עד שתחבר את הסורק (מחק אותה אחר כך):
        watchlist = ['NVDA', 'AAPL', 'MSFT', 'TSLA', 'AMD'] 
        
        if not watchlist:
            print("⚠️ Watchlist is empty. Exiting.")
            return
            
        print(f"📋 Watchlist for today: {watchlist}")
        
    except Exception as e:
        print(f"❌ Error fetching watchlist: {e}")
        return

    # שלב 2: הפעלת הבוט מול אלפקה
    try:
        # אתחול הבוט (ימשוך אוטומטית את מפתחות ה-API ממשתני הסביבה)
        trader = PaperTrader()
        
        # אופציונלי: שליחת סיכום מצב תיק נוכחי לטלגרם לפני המסחר
        trader.send_portfolio_summary_alert()
        
        # הרצת הסריקה וחיפוש עסקאות חדשות
        trader.run_daily_scan(watchlist)
        
    except ValueError as ve:
        print(ve) # מדפיס שגיאה אם חסרים מפתחות API
    except Exception as e:
        print(f"❌ Error during trading execution: {e}")

if __name__ == "__main__":
    main()