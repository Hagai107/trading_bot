import sqlite3
import yfinance as yf
import pandas as pd
from database import get_setting

class PaperTrader:
    def __init__(self, db_path="portfolio.db"):
        self.db_path = db_path

    def get_portfolio_summary(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cash = float(get_setting('cash', 10000.0))
        
        cursor.execute("SELECT symbol, shares, current_price FROM positions")
        positions = cursor.fetchall()
        
        positions_value = sum(shares * current_price for _, shares, current_price in positions)
        total_value = cash + positions_value
        
        conn.close()
        return total_value, cash, positions_value

    def run_daily_scan(self, watchlist):
        print(f"\n🚀 Starting automated daily scan for watchlist: {watchlist}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. בדיקת מגבלת פוזיציות מקסימלית
        max_positions = int(get_setting('max_positions', 3))
        cursor.execute("SELECT COUNT(*) FROM positions")
        current_positions_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT symbol FROM positions")
        open_symbols = [row[0] for row in cursor.fetchall()]

        print(f"📊 Current Active Positions ({current_positions_count}/{max_positions}): {open_symbols}")

        if current_positions_count >= max_positions:
            msg = f"⚠️ [SKIP ALL] Max concurrent positions limit ({max_positions}) reached."
            print(msg)
            conn.close()
            return msg

        # 2. מעבר על כל מניה ברשימה
        trades_executed = 0
        for symbol in watchlist:
            print(f"\n🔍 Analyzing {symbol}...")

            # האם המניה כבר מוחזקת בתיק?
            if symbol in open_symbols:
                print(f"   [SKIP] {symbol}: Already held in active portfolio.")
                continue

            # שליפת נתוני מחיר היסטוריים מ-yfinance
            try:
                df = yf.download(symbol, period="60d", interval="1d", progress=False)
                if df.empty or len(df) < 20:
                    print(f"   [SKIP] {symbol}: Insufficient price history data.")
                    continue

                # טיפול במבנה Dataframe במידה ומוחזר MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                close_prices = df['Close']
                last_price = float(close_prices.iloc[-1])
                
                # חישוב אינדיקטורים: SMA20 ו-RSI 14
                sma20 = float(close_prices.rolling(window=20).mean().iloc[-1])
                
                delta = close_prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = float((100 - (100 / (1 + rs))).iloc[-1])

                print(f"   📈 Metrics -> Price: ${last_price:.2f} | SMA20: ${sma20:.2f} | RSI(14): {rsi:.1f}")

                # בדיקת קריטריוני כניסה
                if last_price < sma20:
                    print(f"   [SKIP] {symbol}: Price (${last_price:.2f}) below SMA20 (${sma20:.2f}). Trend is not bullish.")
                    continue

                if rsi > 60:
                    print(f"   [SKIP] {symbol}: RSI ({rsi:.1f}) is above 60 (Overbought / Not in entry zone).")
                    continue

                if rsi < 30:
                    print(f"   [SKIP] {symbol}: RSI ({rsi:.1f}) is below 30 (Downtrend momentum).")
                    continue

                # בדיקת מזומן זמין
                total_val, cash, _ = self.get_portfolio_summary()
                pos_size_pct = float(get_setting('pos_size_pct', 5)) / 100.0
                allocation_amount = total_val * pos_size_pct

                if cash < allocation_amount:
                    print(f"   [SKIP] {symbol}: Insufficient available cash (${cash:.2f} < required ${allocation_amount:.2f}).")
                    continue

                # אם כל התנאים התקיימו - ביצוע קנייה
                shares_to_buy = allocation_amount / last_price
                stop_loss_pct = float(get_setting('stop_loss_pct', 3.0)) / 100.0
                take_profit_pct = float(get_setting('take_profit_pct', 8.0)) / 100.0

                stop_loss = last_price * (1 - stop_loss_pct)
                take_profit = last_price * (1 + take_profit_pct)

                cursor.execute("""
                    INSERT INTO positions (symbol, shares, entry_price, current_price, stop_loss, take_profit)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (symbol, shares_to_buy, last_price, last_price, stop_loss, take_profit))

                cursor.execute("""
                    INSERT INTO trades_history (symbol, action, shares, price, pnl)
                    VALUES (?, 'BUY', ?, ?, 0.0)
                """, (symbol, shares_to_buy, last_price))

                # עדכון יתרת המזומן
                new_cash = cash - allocation_amount
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('cash', ?)", (str(new_cash),))

                conn.commit()
                open_symbols.append(symbol)
                current_positions_count += 1
                trades_executed += 1

                print(f"   ✅ [BUY EXECUTED] {symbol}: Bought {shares_to_buy:.2f} shares at ${last_price:.2f}")

                if current_positions_count >= max_positions:
                    print(f"\n⚠️ Reached maximum position limit ({max_positions}). Stopping scan.")
                    break

            except Exception as e:
                print(f"   ❌ [ERROR] Failed analyzing {symbol}: {e}")

        conn.close()
        summary_msg = f"Daily scan finished. Executed {trades_executed} new trade(s)."
        print(f"\n🏁 {summary_msg}")
        return summary_msg