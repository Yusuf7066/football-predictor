# --- app.py (modular + clean) ---

from flask import Flask, render_template, request, redirect, flash, session
import requests
import sqlite3
import os
from datetime import datetime, timedelta
from twilio.rest import Client
from dotenv import load_dotenv
from dateutil import parser
import random

from routes.my_predictions import register_prediction_history_route

# Load environment variables
load_dotenv()
def ensure_tables_exist():
    with sqlite3.connect("predictions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            match_id TEXT,
            match_date TEXT DEFAULT '',
            home_team TEXT DEFAULT '',
            away_team TEXT DEFAULT '',
            prediction_type TEXT,
            predicted_score TEXT,
            result TEXT DEFAULT '',
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            user TEXT PRIMARY KEY,
            points INTEGER DEFAULT 0
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

# Run it on app start
ensure_tables_exist()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")

def initialize_database():
    with sqlite3.connect("predictions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                match_id TEXT,
                prediction_type TEXT,
                predicted_score TEXT,
                result TEXT DEFAULT '',
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                user TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0
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
        conn.commit()

# ✅ Call the function immediately to auto-create tables
initialize_database()
# Constants
API_KEY = os.getenv("FOOTBALL_API_KEY", "4d4c6417caf14623ad1b8b000838c1f0")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "34f02634f5d5f77cc05a58a691205980")
MATCHES_URL = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
RESULTS_URL = "https://api.football-data.org/v4/competitions/PL/matches?status=FINISHED"
STANDINGS_URL = "https://api.football-data.org/v4/competitions/PL/standings"

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
if ACCOUNT_SID and AUTH_TOKEN:
    print("✅ Twilio SID Loaded:", ACCOUNT_SID[:5] + "...")
    print("✅ Twilio Token Loaded:", AUTH_TOKEN[:5] + "...")
else:
    print("❌ Missing Twilio credentials. Please check your .env and make sure `load_dotenv()` is working.")
FROM_WA = "whatsapp:+14155238886"
client = Client(ACCOUNT_SID, AUTH_TOKEN)

headers = {
    "X-Auth-Token": API_KEY,
    "Content-Type": "application/json"
}

def normalize_name(name):
    return name.lower().replace(" fc", "").replace(".", "").strip()

def get_team_rankings():
    response = requests.get(STANDINGS_URL, headers=headers)
    rankings = {}
    data = response.json()
    if 'standings' in data:
        table = data['standings'][0]['table']
    for team in table:
        rankings[normalize_name(team['team']['name'])] = team['position']

        return rankings
    else:
        print("⚠️ Warning: Standings missing in API response", data)

def get_odds_data():
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?regions=uk&markets=h2h&apiKey={ODDS_API_KEY}"
    response = requests.get(url)
    odds = {}
    if response.status_code == 200:
        for game in response.json():
            home = normalize_name(game['home_team'])
            away = normalize_name(game['away_team'])
            if game.get('bookmakers') and game['bookmakers'][0].get('markets'):
                outcomes = game['bookmakers'][0]['markets'][0]['outcomes']
                match_odds = {normalize_name(o['name']): o['price'] for o in outcomes}
                odds[(home, away)] = {
                    "home_odds": match_odds.get(home),
                    "draw_odds": match_odds.get("draw"),
                    "away_odds": match_odds.get(away)
                }
    return odds
def get_match_predictions():
    rankings = get_team_rankings()
    odds_data = get_odds_data()
    matches = []
    response = requests.get(MATCHES_URL, headers=headers)
    if response.status_code != 200:
        return matches
    for match in response.json().get("matches", []):
        home, away = match['homeTeam']['name'], match['awayTeam']['name']
        home_norm, away_norm = normalize_name(home), normalize_name(away)
        home_rank, away_rank = rankings.get(home_norm), rankings.get(away_norm)
        if not home_rank or not away_rank:
            continue
        diff = away_rank - home_rank
        prediction = "Home Win" if diff >= 3 else "Draw" if -2 <= diff <= 2 else "Away Win"
        odds = odds_data.get((home_norm, away_norm), {})
        if all(odds.get(k) for k in ("home_odds", "draw_odds", "away_odds")):
            best_odds = {
                "Home Win": odds["home_odds"],
                "Draw": odds["draw_odds"],
                "Away Win": odds["away_odds"]
            }
            bookmaker_favorite = min(best_odds, key=best_odds.get)
            matches.append({
                "match_id": str(match['id']),
                "home": home,
                "away": away,
                "date": match['utcDate'][:10],
                "utc_datetime": datetime.strptime(match['utcDate'], "%Y-%m-%dT%H:%M:%SZ"),
                "prediction": prediction,
                "home_odds": odds["home_odds"],
                "draw_odds": odds["draw_odds"],
                "away_odds": odds["away_odds"],
                "value_bet": prediction != bookmaker_favorite
            })
    return matches

# Register modular routes
from routes.auth import register_auth_routes
from routes.predictions import register_prediction_routes
from routes.my_predictions import register_prediction_history_route, register_edit_prediction_route
from routes.leaderboard import register_leaderboard_routes


register_auth_routes(app, client, FROM_WA)
register_prediction_routes(app, headers)
register_leaderboard_routes(app, headers, RESULTS_URL)
register_prediction_history_route(app, headers)
register_edit_prediction_route(app)
  # ✅ pass headers


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True)

