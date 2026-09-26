import os
import pandas as pd
import requests
from datetime import datetime, timedelta

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

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
    def __init__(self):
        # משיכת מפתחות ה-API מתוך משתני הסביבה
        self.api_key = os.getenv('APCA_API_KEY_ID')
        self.api_secret = os.getenv('APCA_API_SECRET_KEY')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("❌ Alpaca API keys missing! Please set APCA_API_KEY_ID and APCA_API_SECRET_KEY.")

        # התחברות ללקוח המסחר (paper=True לסימולציה) וללקוח הנתונים
        self.trading_client = TradingClient(self.api_key, self.api_secret, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.api_secret)
        
        # הגדרות אסטרטגיה
        self.max_positions = 15
        self.take_profit_pct = 0.06  # 6% רווח
        self.stop_loss_pct = 0.03    # 3% הפסד

    def check_and_notify_closed_sales(self):
        """בדיקה ושליחת התראות טלגרם על מכירות שבוצעו ב-24 השעות האחרונות"""
        print('\n🔍 Checking for executed sell orders in the last 24 hours...')
        try:
            # שליפת פקודות מכירה שנסגרו ביממה האחרונה
            filter_params = GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                side=OrderSide.SELL,
                after=datetime.now() - timedelta(days=1)
            )
            closed_orders = self.trading_client.get_orders(filter_params)
            
            if not closed_orders:
                print('ℹ️ No closed sell orders in the last 24 hours.')
                return

            for order in closed_orders:
                # וודאות שהפקודה אכן התבצעה בפועל (Filled)
                if str(order.status).lower() != 'filled':
                    continue
                
                symbol = order.symbol
                qty = float(order.qty) if order.qty else 0.0
                filled_price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
                order_type = str(order.order_type).lower()
                
                # זיהוי סוג הסגירה: רווח (Limit) או הפסד (Stop/Stop Limit)
                if 'limit' in order_type:
                    type_str = "🎯 *TAKE PROFIT HIT (+6%)*"
                elif 'stop' in order_type:
                    type_str = "🛑 *STOP LOSS HIT (-3%)*"
                else:
                    type_str = "📉 *SELL EXECUTED*"

                alert_msg = (
                    f"{type_str}\n"
                    f"• *Symbol:* `{symbol}`\n"
                    f"• *Executed Price:* `${filled_price:.2f}`\n"
                    f"• *Shares Sold:* `{qty}`\n"
                    f"• *Order Type:* `{order_type.upper()}`"
                )
                send_telegram_alert(alert_msg)
                print(f'   📲 Telegram alert sent for closed sale: {symbol}')

        except Exception as e:
            print(f'⚠️ Error checking closed sell orders: {e}')

    def send_portfolio_summary_alert(self):
        """שליחת דוח מצב התיק מול שרתי אלפקה + התראות מכירה"""
        # בדיקת מכירות שבוצעו ושליחת התראות ייעודיות
        self.check_and_notify_closed_sales()

        print('\n📲 Generating portfolio summary from Alpaca...')
        
        try:
            account = self.trading_client.get_account()
            positions = self.trading_client.get_all_positions()
            
            total_equity = float(account.equity)
            cash = float(account.buying_power)
            
            positions_details = []
            for pos in positions:
                symbol = pos.symbol
                qty = float(pos.qty)
                entry_price = float(pos.avg_entry_price)
                current_price = float(pos.current_price)
                pnl_pct = float(pos.unrealized_plpc) * 100 if pos.unrealized_plpc else 0.0

                
                pnl_icon = '🟢' if pnl_pct >= 0 else '🔴'
                positions_details.append(
                    f'• *{symbol}*: `{qty}` מניות\n'
                    f'  כניסה: `${entry_price:.2f}` | נוכחי: `${current_price:.2f}` ({pnl_icon} `{pnl_pct:+.2f}%`)'
                )

            msg = f'📊 *דוח מצב תיק יומי (Alpaca Paper)*\n\n'
            msg += f'💰 *שווי תיק כולל:* `${total_equity:,.2f}`\n'
            msg += f'💵 *כוח קנייה פנוי:* `${cash:,.2f}`\n'
            msg += f'📦 *פוזיציות פתוחות:* `{len(positions)}/{self.max_positions}`\n\n'

            if positions_details:
                msg += '*📋 פירוט פוזיציות:*\n' + '\n\n'.join(positions_details)
            else:
                msg += 'ℹ️ *אין פוזיציות פתוחות כרגע בתיק.*'

            send_telegram_alert(msg)
            print('✅ Portfolio summary sent.')
            
        except Exception as e:
            print(f'❌ Error fetching portfolio summary: {e}')

    def run_daily_scan(self, watchlist):
        print(f'\n🚀 Starting daily execution for watchlist: {watchlist}')

        # קבלת מצב החשבון והפוזיציות הפתוחות
        account = self.trading_client.get_account()
        open_positions = self.trading_client.get_all_positions()
        
        current_positions_count = len(open_positions)
        open_symbols = [pos.symbol for pos in open_positions]
        total_equity = float(account.equity)

        print(f'📊 Active Positions ({current_positions_count}/{self.max_positions}): {open_symbols}')

        if current_positions_count >= self.max_positions:
            msg = f'⚠️ [SKIP ALL] Max concurrent positions limit ({self.max_positions}) reached.'
            print(msg)
            return msg

        trades_executed = 0
        
        # חישוב תקציב קבוע לפוזיציה (תיק מחולק ל-15 מנות שוות)
        position_budget = total_equity / self.max_positions

        for symbol in watchlist:
            print(f'\n🔍 Analyzing {symbol}...')

            if symbol in open_symbols:
                print(f'   [SKIP] {symbol}: Already held in portfolio.')
                continue

            try:
                # משיכת נתונים היסטוריים מאלפקה
                request_params = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Day,
                    start=datetime.now() - timedelta(days=90)
                )
                bars = self.data_client.get_stock_bars(request_params)
                
                if not bars or bars.df.empty:
                    print(f'   [SKIP] {symbol}: No price data returned from Alpaca.')
                    continue

                # חילוץ הנתונים עבור המניה הספציפית
                df = bars.df.xs(symbol, level=0)
                if len(df) < 20:
                    print(f'   [SKIP] {symbol}: Insufficient historical data.')
                    continue

                close_prices = df['close']
                last_price = float(close_prices.iloc[-1])
                sma20 = float(close_prices.rolling(window=20).mean().iloc[-1])

                # חישוב RSI (14)
                delta = close_prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = float((100 - (100 / (1 + rs))).iloc[-1])

                print(f'  📈 Price: ${last_price:.2f} | SMA20:${sma20:.2f} | RSI: {rsi:.1f}')

                # לוגיקה למסחר
                if last_price < sma20:
                    print(f'   [SKIP] {symbol}: Below SMA20.')
                    continue

                if rsi > 60 or rsi < 30:
                    print(f'   [SKIP] {symbol}: RSI ({rsi:.1f}) outside 30-60 zone.')
                    continue

                # בדיקת כוח קנייה באלפקה (Buying Power)
                buying_power = float(self.trading_client.get_account().buying_power)
                if buying_power < position_budget:
                    print(f'   [SKIP] {symbol}: Insufficient buying power in Alpaca account.')
                    continue

                # חישוב כמות המניות לקנייה
                qty = int(position_budget // last_price)
                if qty <= 0:
                    print(f'   [SKIP] {symbol}: Price too high for allocated budget.')
                    continue

                # חישוב שערים ל-Bracket Order
                stop_loss_price = round(last_price * (1 - self.stop_loss_pct), 2)
                take_profit_price = round(last_price * (1 + self.take_profit_pct), 2)

                # הרכבת ושליחת פקודת Bracket לאלפקה
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC,
                    order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=take_profit_price),
                    stop_loss=StopLossRequest(stop_price=stop_loss_price)
                )

                self.trading_client.submit_order(order_data)
                
                open_symbols.append(symbol)
                current_positions_count += 1
                trades_executed += 1

                print(f'   ✅ [BUY EXECUTED] {symbol} (Qty: {qty}) at ~${last_price:.2f}')

                alert_msg = (
                    f"🚀 *BUY EXECUTED (Alpaca)*\n"
                    f"• *Symbol:* `{symbol}`\n"
                    f"• *Price:* `~${last_price:.2f}`\n"
                    f"• *Shares:* `{qty}`\n"
                    f"• *Stop Loss (-3%):* `${stop_loss_price:.2f}`\n"
                    f"• *Take Profit (+8%):* `${take_profit_price:.2f}`"
                )
                send_telegram_alert(alert_msg)

                if current_positions_count >= self.max_positions:
                    print(f'\n⚠️ Reached max positions ({self.max_positions}). Stopping.')
                    break

            except Exception as e:
                print(f'   ❌ [ERROR] {symbol}: {e}')

        summary_msg = f'Daily scan finished. Executed {trades_executed} new trade(s).'
        print(f'\n🏁 {summary_msg}')
        return summary_msg
