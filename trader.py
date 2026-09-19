import os
import sqlite3
import pandas as pd
import requests
import yfinance as yf
from database import get_setting


def send_telegram_alert(message):
  token = os.getenv('TELEGRAM_TOKEN')
  chat_id = os.getenv('TELEGRAM_CHAT_ID')

  if token and chat_id:
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    try:
      requests.post(url, json=payload, timeout=5)
    except Exception as e:
      print(f'⚠️ Failed to send Telegram notification: {e}')


class PaperTrader:

  def __init__(self, db_path='portfolio.db'):
    self.db_path = db_path

  def get_portfolio_summary(self):
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    cash = float(get_setting('cash', 10000.0))
    cursor.execute('SELECT symbol, shares, current_price FROM positions')
    positions = cursor.fetchall()
    positions_value = sum(
        shares * current_price for _, shares, current_price in positions
    )
    total_value = cash + positions_value
    conn.close()
    return total_value, cash, positions_value

  def check_and_close_positions(self):
    """בדיקת פוזיציות קיימות ומכירה אוטומטית במידה והגיעו ל-Stop Loss או Take Profit"""
    print('\n🛡️ Checking open positions for Stop Loss / Take Profit...')
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    cursor.execute(
        'SELECT symbol, shares, entry_price, stop_loss, take_profit FROM'
        ' positions'
    )
    positions = cursor.fetchall()

    closed_count = 0
    for symbol, shares, entry_price, stop_loss, take_profit in positions:
      try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period='1d')
        if history.empty:
          continue

        current_price = float(history['Close'].iloc[-1])

        # עדכון מחיר נוכחי ב-DB
        cursor.execute(
            'UPDATE positions SET current_price = ? WHERE symbol = ?',
            (current_price, symbol),
        )

        reason = None
        if current_price <= stop_loss:
          reason = '🛡️ STOP LOSS HIT'
        elif current_price >= take_profit:
          reason = '🎯 TAKE PROFIT HIT'

        if reason:
          sell_value = shares * current_price
          pnl_cash = (current_price - entry_price) * shares
          pnl_pct = ((current_price - entry_price) / entry_price) * 100.0

          # 1. מחיקת הפוזיציה
          cursor.execute(
              'DELETE FROM positions WHERE symbol = ?', (symbol,)
          )

          # 2. תיעוד בהיסטוריית הטריידים
          cursor.execute(
              """
                        INSERT INTO trades_history (symbol, action, shares, price, pnl)
                        VALUES (?, 'SELL', ?, ?, ?)
                    """,
              (symbol, shares, current_price, pnl_cash),
          )

          # 3. עדכון מזומן פנוי
          cash = float(get_setting('cash', 10000.0))
          new_cash = cash + sell_value
          cursor.execute(
              "INSERT OR REPLACE INTO settings (key, value) VALUES ('cash', ?)",
              (str(new_cash),),
          )

          conn.commit()
          closed_count += 1

          pnl_icon = '🟢' if pnl_cash >= 0 else '🔴'
          print(
              f'   💥 [SELL EXECUTED] {symbol} at ${current_price:.2f}'
              f' ({reason})'
          )

          alert_msg = (
              f'💥 *SELL EXECUTED* ({reason})\n• *Symbol:* `{symbol}`\n• *Exit'
              f' Price:* `${current_price:.2f}`\n• *PnL:* `{pnl_icon}'
              f' ${pnl_cash:+.2f} ({pnl_pct:+.2f}%)`'
          )
          send_telegram_alert(alert_msg)

      except Exception as e:
        print(f'   ❌ Error checking exit condition for {symbol}: {e}')

    conn.close()
    return closed_count

  def update_live_prices(self):
    """עדכון מחירי השוק העדכניים בלייב עבור הפוזיציות הפתוחות ב-DB"""
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT symbol FROM positions')
    open_positions = cursor.fetchall()

    for (symbol,) in open_positions:
      try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period='1d')
        if not history.empty:
          last_price = float(history['Close'].iloc[-1])
          cursor.execute(
              'UPDATE positions SET current_price = ? WHERE symbol = ?',
              (last_price, symbol),
          )
      except Exception as e:
        print(f'⚠️ Could not update live price for {symbol}: {e}')

    conn.commit()
    conn.close()

  def send_portfolio_summary_alert(self):
    """שליחת דוח מצב התיק המלא בטלגרם"""
    print('\n📲 Generating and sending daily portfolio summary alert...')

    self.update_live_prices()

    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    cash = float(get_setting('cash', 10000.0))
    cursor.execute(
        'SELECT symbol, shares, entry_price, current_price, stop_loss,'
        ' take_profit FROM positions'
    )
    positions = cursor.fetchall()

    positions_value = 0.0
    positions_details = []

    for symbol, shares, entry_price, current_price, sl, tp in positions:
      pos_val = shares * current_price
      positions_value += pos_val

      pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
      pnl_icon = '🟢' if pnl_pct >= 0 else '🔴'

      positions_details.append(
          f'• *{symbol}*: `{shares:.2f}` מניות\n'
          f'  מחיר כניסה: `${entry_price:.2f}` | נוכחי: `${current_price:.2f}`'
          f' ({pnl_icon} `{pnl_pct:+.2f}%`)\n'
          f'  🎯 TP: `${tp:.2f}` | 🛡️ SL: `${sl:.2f}`'
      )

    total_value = cash + positions_value
    initial_cash = 10000.0
    total_pnl_pct = ((total_value - initial_cash) / initial_cash) * 100.0
    total_pnl_icon = '📈' if total_pnl_pct >= 0 else '📉'

    conn.close()

    msg = f'📊 *דוח מצב תיק יומי*\n\n'
    msg += (
        f'💰 *שווי תיק כולל:* `${total_value:,.2f}` ({total_pnl_icon}'
        f' `{total_pnl_pct:+.2f}%`)\n'
    )
    msg += f'💵 *מזומן פנוי:* `${cash:,.2f}`\n'
    msg += (
        f'📦 *שווי פוזיציות:* `${positions_value:,.2f}` (`{len(positions)}`'
        ' פוזיציות פתוחות)\n\n'
    )

    if positions_details:
      msg += '*📋 פוזיציות פתוחות בתיק:*\n' + '\n\n'.join(positions_details)
    else:
      msg += 'ℹ️ *אין פוזיציות פתוחות כרגע בתיק.*'

    send_telegram_alert(msg)
    print('✅ Portfolio summary sent successfully via Telegram.')

  def run_daily_scan(self, watchlist):
    # 1. בדיקה ומכירה אוטומטית של פוזיציות שהגיעו ל-SL/TP
    self.check_and_close_positions()

    # 2. סריקת קנייה
    print(f'\n🚀 Starting daily execution for watchlist: {watchlist}')

    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    max_positions = int(get_setting('max_positions', 7))
    cursor.execute('SELECT COUNT(*) FROM positions')
    current_positions_count = cursor.fetchone()[0]

    cursor.execute('SELECT symbol FROM positions')
    open_symbols = [row[0] for row in cursor.fetchall()]

    print(
        f'📊 Active Positions ({current_positions_count}/{max_positions}):'
        f' {open_symbols}'
    )

    if current_positions_count >= max_positions:
      msg = (
          '⚠️ [SKIP ALL] Max concurrent positions limit'
          f' ({max_positions}) reached.'
      )
      print(msg)
      conn.close()
      return msg

    trades_executed = 0
    for symbol in watchlist:
      print(f'\n🔍 Analyzing {symbol}...')

      if symbol in open_symbols:
        print(f'   [SKIP] {symbol}: Already held in portfolio.')
        continue

      try:
        shares_to_buy = 0.0

        df = yf.download(symbol, period='60d', interval='1d', progress=False)
        if df.empty or len(df) < 20:
          print(f'   [SKIP] {symbol}: Insufficient price data.')
          continue

        if isinstance(df.columns, pd.MultiIndex):
          df.columns = df.columns.get_level_values(0)

        close_prices = df['Close']
        last_price = float(close_prices.iloc[-1])
        sma20 = float(close_prices.rolling(window=20).mean().iloc[-1])

        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        print(
            f'   📈 Price: ${last_price:.2f} \vert{} SMA20:${sma20:.2f} | RSI:'
            f' {rsi:.1f}'
        )

        if last_price < sma20:
          print(f'   [SKIP] {symbol}: Below SMA20.')
          continue

        if rsi > 60 or rsi < 30:
          print(
              f'   [SKIP] {symbol}: RSI ({rsi:.1f}) outside 30-60 target zone.'
          )
          continue

        total_val, cash, _ = self.get_portfolio_summary()
        pos_size_pct = float(get_setting('pos_size_pct', 5)) / 100.0
        allocation_amount = total_val * pos_size_pct

        if cash < allocation_amount:
          print(f'   [SKIP] {symbol}: Insufficient cash.')
          continue

        shares_to_buy = allocation_amount / last_price
        stop_loss_pct = float(get_setting('stop_loss_pct', 3.0)) / 100.0
        take_profit_pct = float(get_setting('take_profit_pct', 8.0)) / 100.0

        stop_loss = last_price * (1 - stop_loss_pct)
        take_profit = last_price * (1 + take_profit_pct)

        cursor.execute(
            """
                    INSERT INTO positions (symbol, shares, entry_price, current_price, stop_loss, take_profit)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
            (
                symbol,
                shares_to_buy,
                last_price,
                last_price,
                stop_loss,
                take_profit,
            ),
        )

        cursor.execute(
            """
                    INSERT INTO trades_history (symbol, action, shares, price, pnl)
                    VALUES (?, 'BUY', ?, ?, 0.0)
                """,
            (symbol, shares_to_buy, last_price),
        )

        new_cash = cash - allocation_amount
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('cash', ?)",
            (str(new_cash),),
        )

        conn.commit()
        open_symbols.append(symbol)
        current_positions_count += 1
        trades_executed += 1

        print(f'   ✅ [BUY EXECUTED] {symbol} at ${last_price:.2f}')

        alert_msg = (
            '🚀 *BUY EXECUTED*\n• *Symbol:* `'
            f' {symbol}`\n• *Price:* `${last_price:.2f}`\n• *Shares:* `'
            f' {shares_to_buy:.2f}`\n• *Stop Loss:* `${stop_loss:.2f}`\n•'
            f' *Take Profit:* `${take_profit:.2f}`'
        )
        send_telegram_alert(alert_msg)

        if current_positions_count >= max_positions:
          print(f'\n⚠️ Reached max positions ({max_positions}). Stopping.')
          break

      except Exception as e:
        print(f'   ❌ [ERROR] {symbol}: {e}')

    conn.close()
    summary_msg = (
        f'Daily scan finished. Executed {trades_executed} new trade(s).'
    )
    print(f'\n🏁 {summary_msg}')
    return summary_msg