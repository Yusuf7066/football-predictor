import sqlite3

# Connect (creates the file if it doesn't exist)
conn = sqlite3.connect("predictions.db")
cursor = conn.cursor()

# Create predictions table
cursor.execute("""
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    match_id TEXT NOT NULL,
    prediction_type TEXT NOT NULL,
    predicted_score TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    locked BOOLEAN DEFAULT 0
)
""")

conn.commit()
conn.close()

print("✅ Database initialized successfully!")
