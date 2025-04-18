import sqlite3

with sqlite3.connect("predictions.db") as conn:
    cursor = conn.cursor()

    # Create or ensure predictions table exists
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

    # Create or ensure otp_sessions exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_sessions (
            nickname TEXT PRIMARY KEY,
            phone_number TEXT,
            otp TEXT,
            expires_at TEXT
        )
    """)

    # ✅ Add resend_count if it doesn't exist
    cursor.execute("PRAGMA table_info(otp_sessions)")
    columns = [col[1] for col in cursor.fetchall()]
    if "resend_count" not in columns:
        cursor.execute("ALTER TABLE otp_sessions ADD COLUMN resend_count INTEGER DEFAULT 0")
        print("✅ Added resend_count column to otp_sessions")
    else:
        print("ℹ️ resend_count already exists")

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

print("✅ Database initialized successfully.")
