import sqlite3

def add_column_if_missing(cursor, table, column, col_type_default):
    cursor.execute(f"PRAGMA table_info({table})")
    existing_cols = [col[1] for col in cursor.fetchall()]
    if column not in existing_cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type_default}")
        print(f"✅ Added missing column: {column} to {table}")
    else:
        print(f"ℹ️ Column '{column}' already exists in '{table}'")

with sqlite3.connect("predictions.db") as conn:
    cursor = conn.cursor()

    # Predictions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            match_id TEXT,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,
            match_time TEXT,
            prediction_type TEXT,
            predicted_score TEXT,
            result TEXT DEFAULT '',
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # OTP Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_sessions (
            nickname TEXT PRIMARY KEY,
            phone_number TEXT,
            otp TEXT,
            expires_at TEXT
        )
    """)
    # Add resend_count if missing
    add_column_if_missing(cursor, "otp_sessions", "resend_count", "INTEGER DEFAULT 0")

    # Leaderboard table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            score INTEGER DEFAULT 0,
            perfect_scores INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    print("✅ All tables and columns are verified.")

conn.commit()
print("✅ predictions.db initialized successfully.")
