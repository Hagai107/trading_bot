import sqlite3
import pandas as pd
import yfinance as yf
from database import get_connection, get_setting, set_setting
from strategy import analyze_stock, filter_volume

class PaperTrader:
    def __init__(self):
        pass

    def get_portfolio_summary(self):
        conn = get_connection()
        cash = get_setting('cash', 10000.0)
        
        positions_df = pd.read_sql("SELECT * FROM positions", conn)
        conn.close()
        
        positions_val = 0.0
        if not positions_df.empty:
            for _, row in positions_df.iterrows():
                try:
                    ticker = yf.Ticker(row['symbol'])
                    live_price = float(ticker.history(period="1d")['Close'].iloc[-1])
                except Exception:
                    live_price = float(row['entry_price'])
                positions_val += live_price * float(row['shares'])
                
        total_val = cash + positions_val
        return total_val, cash, positions_val

    def check_max_daily_loss(self, current_total_val):
        """Enforces maximum allowed daily loss rule."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT total_value FROM portfolio_history ORDER BY date DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] > 0:
            start_day_val = row[0]
            daily_loss_pct = ((start_day_val - current_total_val) / start_day_val) * 100
            max_allowed_loss = get_setting('max_daily_loss_pct', 2.0)
            if daily_loss_pct >= max_allowed_loss:
                print(f"⚠️ Trading halted! Daily drawdown reached {daily_loss_pct:.2f}% (Limit: {max_allowed_loss}%).")
                return True
        return False

    def update_positions_and_check_sl_tp(self):
        """Updates market prices and triggers Stop-Loss / Take-Profit."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT symbol, shares, entry_price, stop_loss, take_profit FROM positions")
        positions = cursor.fetchall()
        
        for symbol, shares, entry_p, sl, tp in positions:
            try:
                live_price = float(yf.Ticker(symbol).history(period="1d")['Close'].iloc[-1])
            except Exception:
                continue

            cursor.execute("UPDATE positions SET current_price = ? WHERE symbol = ?", (live_price, symbol))
            
            pnl = (live_price - entry_p) * shares
            pnl_pct = ((live_price - entry_p) / entry_p) * 100
            
            if live_price <= sl:
                self.close_position(symbol, shares, live_price, pnl, pnl_pct, "Stop Loss Triggered")
            elif live_price >= tp:
                self.close_position(symbol, shares, live_price, pnl, pnl_pct, "Take Profit Triggered")
                
        conn.commit()
        conn.close()

    def close_position(self, symbol, shares, price, pnl, pnl_pct, reason):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        
        sale_amount = shares * price
        current_cash = get_setting('cash', 10000.0)
        set_setting('cash', current_cash + sale_amount)
        
        cursor.execute("""
            INSERT INTO trades_history (symbol, action, shares, price, pnl, pnl_percent, reason)
            VALUES (?, 'SELL', ?, ?, ?, ?, ?)
        """, (symbol, shares, price, pnl, pnl_pct, reason))
        
        conn.commit()
        conn.close()

    def execute_buy(self, symbol, price, reason):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM positions")
        open_pos_count = cursor.fetchone()[0]
        max_pos = get_setting('max_positions', 3.0)
        
        if open_pos_count >= max_pos:
            conn.close()
            return False, "Max open positions limit reached"

        cursor.execute("SELECT symbol FROM positions WHERE symbol = ?", (symbol,))
        if cursor.fetchone():
            conn.close()
            return False, "Symbol already in portfolio"

        total_val, cash, _ = self.get_portfolio_summary()
        pos_size_pct = get_setting('pos_size_pct', 5.0)
        target_allocation = total_val * (pos_size_pct / 100.0)

        if cash < target_allocation:
            target_allocation = cash

        if target_allocation < 50:
            conn.close()
            return False, "Insufficient cash for position allocation"

        shares = round(target_allocation / price, 4)
        sl_pct = get_setting('stop_loss_pct', 3.0)
        tp_pct = get_setting('take_profit_pct', 8.0)
        
        stop_loss = round(price * (1 - sl_pct / 100.0), 2)
        take_profit = round(price * (1 + tp_pct / 100.0), 2)

        set_setting('cash', cash - (shares * price))

        cursor.execute("""
            INSERT INTO positions (symbol, shares, entry_price, current_price, stop_loss, take_profit)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (symbol, shares, price, price, stop_loss, take_profit))

        cursor.execute("""
            INSERT INTO trades_history (symbol, action, shares, price, pnl, pnl_percent, reason)
            VALUES (?, 'BUY', ?, ?, 0, 0, ?)
        """, (symbol, shares, price, reason))

        conn.commit()
        conn.close()
        return True, f"Bought {shares} shares of {symbol} at ${price}"

    def run_daily_scan(self, watch_list):
        total_val, cash, pos_val = self.get_portfolio_summary()
        
        if self.check_max_daily_loss(total_val):
            return "Trading Halted: Maximum daily loss limit triggered."

        self.update_positions_and_check_sl_tp()

        for symbol in watch_list:
            if not filter_volume(symbol, min_avg_volume=500000):
                continue

            signal, price, reason = analyze_stock(symbol)
            if signal == "BUY":
                self.execute_buy(symbol, price, reason)

        today_str = pd.Timestamp.now().strftime('%Y-%m-%d')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO portfolio_history (date, total_value, cash, positions_value, daily_pnl)
            VALUES (?, ?, ?, ?, 0)
        """, (today_str, total_val, cash, pos_val))
        conn.commit()
        conn.close()

        return "Daily scanning & trading execution completed successfully!"