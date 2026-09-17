from scanner import update_hottest_watchlist
from trader import PaperTrader


def main():
  trader = PaperTrader()

  # 1. סריקה בלייב של השוק ועדכון ה-DB ב-10 המניות החמות של היום
  watchlist = update_hottest_watchlist(top_n=10)

  # 2. הרצת אסטרטגיית המסחר היומית על הרשימה העדכנית
  trader.run_daily_scan(watchlist)

  # 3. שליחת דוח מצב התיק המעודכן לטלגרם
  trader.send_portfolio_summary_alert()


if __name__ == '__main__':
  main()