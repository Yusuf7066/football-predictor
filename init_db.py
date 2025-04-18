import sqlite3

with sqlite3.connect("predictions.db") as conn:
    cursor = conn.cursor()

    # Create or ensure the table structure is complete
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_sessions (
            nickname TEXT PRIMARY KEY,
            phone_number TEXT,
            otp TEXT,
            expires_at TEXT
        )
    """)

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

    print("✅ Database tables are initialized.")

conn.commit()
conn.close()

print("✅ predictions.db initialized with all required tables.")
