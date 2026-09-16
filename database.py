import sqlite3

DB_NAME = "portfolio.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. טבלת פוזיציות פתוחות
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            shares REAL,
            entry_price REAL,
            current_price REAL,
            stop_loss REAL,
            take_profit REAL,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. טבלת היסטוריית עסקאות
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            action TEXT,
            shares REAL,
            price REAL,
            pnl REAL,
            pnl_percent REAL,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. טבלת מעקב שווי תיק יומי (Equity Curve)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_history (
            date DATE PRIMARY KEY,
            total_value REAL,
            cash REAL,
            positions_value REAL,
            daily_pnl REAL
        )
    """)
    
    # 4. טבלת הגדרות דינמיות
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value REAL
        )
    """)
    
    # הגדרת ערכי מחדל ראשוניים אם הטבלה ריקה
    default_settings = [
        ('cash', 10000.0),
        ('pos_size_pct', 5.0),        # 5% מהתיק לעסקה
        ('max_daily_loss_pct', 2.0), # 2% הפסד יומי מקסימלי
        ('max_positions', 3.0),      # מקסימום 3 פוזיציות פתוחות
        ('stop_loss_pct', 3.0),      # 3% Stop Loss
        ('take_profit_pct', 8.0)     # 8% Take Profit
    ]
    
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        
    conn.commit()
    conn.close()

def get_setting(key, default_value=0.0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default_value

def set_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")