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
from routes.leaderboard import register_leaderboard_routes

register_leaderboard_routes(app, headers, RESULTS_URL)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")

# Constants
API_KEY = os.getenv("FOOTBALL_API_KEY", "4d4c6417caf14623ad1b8b000838c1f0")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "34f02634f5d5f77cc05a58a691205980")
MATCHES_URL = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
RESULTS_URL = "https://api.football-data.org/v4/competitions/PL/matches?status=FINISHED"
STANDINGS_URL = "https://api.football-data.org/v4/competitions/PL/standings"

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
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
    if response.status_code == 200:
        data = response.json()
        for team in data['standings'][0]['table']:
            rankings[normalize_name(team['team']['name'])] = team['position']
    return rankings

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



from routes.auth import register_auth_routes
from routes.predictions import register_prediction_routes
from routes.leaderboard import register_leaderboard_routes

# Register blueprint-style route modules
register_auth_routes(app, client, FROM_WA)
register_prediction_routes(app, headers)
register_leaderboard_routes(app, headers)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
