from flask import Flask, render_template, request, redirect, flash, session
from dotenv import load_dotenv
load_dotenv()
from dateutil import parser
import requests
import sqlite3
import os
from datetime import datetime, timedelta
from dateutil import parser
from twilio.rest import Client
import random

app = Flask(__name__)
app.secret_key = "super-secret-key"

API_KEY = "4d4c6417caf14623ad1b8b000838c1f0"
ODDS_API_KEY = "34f02634f5d5f77cc05a58a691205980"
MATCHES_URL = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
RESULTS_URL = "https://api.football-data.org/v4/competitions/PL/matches?status=FINISHED"
STANDINGS_URL = "https://api.football-data.org/v4/competitions/PL/standings"

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_WA = "whatsapp:+14155238886"
client = Client(ACCOUNT_SID, AUTH_TOKEN)
print("TWILIO SID:", ACCOUNT_SID)
print("TWILIO TOKEN:", AUTH_TOKEN[:5] + "***")

headers = {
    "X-Auth-Token": API_KEY,
    "Content-Type": "application/json"
}

# Ensure required tables exist
conn = sqlite3.connect("predictions.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    match_id TEXT NOT NULL,
    prediction_type TEXT NOT NULL,
    predicted_score TEXT NOT NULL,
    ip_address TEXT,
    phone_number TEXT,
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
CREATE TABLE IF NOT EXISTS users (
    nickname TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    otp TEXT,
    otp_expiry DATETIME
)
""")

conn.commit()
conn.close()

def normalize_name(name):
    return name.lower().replace(" fc", "").replace(".", "").strip()

def get_team_rankings():
    response = requests.get(STANDINGS_URL, headers=headers)
    rankings = {}
    if response.status_code == 200:
        data = response.json()
        table = data['standings'][0]['table']
        for team in table:
            rankings[normalize_name(team['team']['name'])] = team['position']
    return rankings

def get_odds_data():
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?regions=uk&markets=h2h&apiKey={ODDS_API_KEY}"
    response = requests.get(url)
    odds = {}

    if response.status_code == 200:
        data = response.json()
        for game in data:
            home = normalize_name(game['home_team'])
            away = normalize_name(game['away_team'])
            key = (home, away)

            if game.get('bookmakers') and game['bookmakers'][0].get('markets'):
                outcomes = game['bookmakers'][0]['markets'][0]['outcomes']
                match_odds = {}
                for outcome in outcomes:
                    match_odds[normalize_name(outcome['name'])] = outcome['price']

                odds[key] = {
                    "home_odds": match_odds.get(home),
                    "draw_odds": match_odds.get("draw"),
                    "away_odds": match_odds.get(away)
                }
    return odds

def get_match_predictions():
    response = requests.get(MATCHES_URL, headers=headers)
    matches = []

    if response.status_code != 200:
        return matches

    match_data = response.json().get("matches", [])
    rankings = get_team_rankings()
    odds_data = get_odds_data()

    for match in match_data:
        home = match['homeTeam']['name']
        away = match['awayTeam']['name']
        date = match['utcDate'][:10]
        match_id = str(match['id'])
        utc_datetime = datetime.strptime(match['utcDate'], "%Y-%m-%dT%H:%M:%SZ")

        home_norm = normalize_name(home)
        away_norm = normalize_name(away)

        home_rank = rankings.get(home_norm)
        away_rank = rankings.get(away_norm)

        if not home_rank or not away_rank:
            continue

        diff = away_rank - home_rank
        if diff >= 3:
            prediction = "Home Win"
        elif -2 <= diff <= 2:
            prediction = "Draw"
        else:
            prediction = "Away Win"

        odds = odds_data.get((home_norm, away_norm), {})

        if odds.get("home_odds") and odds.get("draw_odds") and odds.get("away_odds"):
            matches.append({
                "match_id": match_id,
                "home": home,
                "away": away,
                "date": date,
                "utc_datetime": utc_datetime,
                "prediction": prediction,
                "home_odds": odds["home_odds"],
                "draw_odds": odds["draw_odds"],
                "away_odds": odds["away_odds"]
            })

    return matches

@app.route("/")
def home():
    matches = get_match_predictions()
    return render_template("index.html", matches=matches, utcnow=datetime.utcnow)

@app.route("/predict", methods=["POST"])
def submit_prediction():
    if "nickname" not in session:
        flash("You must be logged in to submit a prediction.")
        return redirect("/login")

    match_id = request.form.get("match_id")
    prediction_type = request.form.get("prediction")
    home_score = request.form.get("home_score")
    away_score = request.form.get("away_score")
    match_time = request.form.get("match_time")
    ip_address = request.remote_addr
    user = session.get("nickname")
    phone = request.form.get("phone", "").strip()

    predicted_score = f"{home_score}-{away_score}"

    try:
        home = int(home_score)
        away = int(away_score)
    except ValueError:
        flash("Invalid score values.")
        return redirect("/")

    if prediction_type == "Home Win" and home <= away:
        flash("⚠️ You chose Home Win, but the score doesn’t match.")
        return redirect("/")
    elif prediction_type == "Draw" and home != away:
        flash("⚠️ You chose Draw, but the score isn’t equal.")
        return redirect("/")
    elif prediction_type == "Away Win" and home >= away:
        flash("⚠️ You chose Away Win, but the score doesn’t match.")
        return redirect("/")

    if datetime.utcnow() >= datetime.strptime(match_time, "%Y-%m-%dT%H:%M:%SZ") - timedelta(minutes=2):
        flash("Prediction window has closed for this match.")
        return redirect("/")

    conn = sqlite3.connect("predictions.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM predictions WHERE match_id = ? AND (user = ? OR ip_address = ?)", (match_id, user, ip_address))
    exists = cursor.fetchone()
    if exists:
        conn.close()
        flash("You’ve already made a prediction for this match.")
        return redirect("/")

    cursor.execute("""
        INSERT INTO predictions (user, match_id, prediction_type, predicted_score, ip_address, phone_number)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user, match_id, prediction_type, predicted_score, ip_address, phone))
    conn.commit()
    conn.close()

    flash("✅ Your prediction has been submitted!")
    return redirect("/")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/send_otp", methods=["POST"])
def send_otp():
    nickname = request.form.get("nickname").strip()
    phone = request.form.get("phone").strip()

    if not nickname or not phone:
        flash("Nickname and phone are required.")
        return redirect("/login")

    otp = f"{random.randint(100000, 999999)}"
    if datetime.utcnow() > parser.parse(expiry):
            flash("❌ OTP expired.")
            return redirect("/login")

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (nickname, phone, otp, otp_expiry)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(nickname) DO UPDATE SET phone=excluded.phone, otp=excluded.otp, otp_expiry=excluded.otp_expiry
    """, (nickname, phone, otp, expiry))
    conn.commit()
    conn.close()

    try:
        client.messages.create(
            from_=FROM_WA,
            body=f"Your Football Predictor login code is: {otp}",
            to=f"whatsapp:{phone}"
        )
        flash("✅ OTP sent to WhatsApp.")
    except Exception as e:
        flash(f"❌ Failed to send OTP: {str(e)}")
        return redirect("/login")

    session["pending_nickname"] = nickname
    return redirect("/verify_otp")

@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "GET":
        return render_template("verify_otp.html", nickname=session.get("pending_nickname"))

    otp_entered = request.form.get("otp").strip()
    nickname = session.get("pending_nickname")

    conn = sqlite3.connect("predictions.db")
    cursor = conn.cursor()
    cursor.execute("SELECT otp, otp_expiry FROM users WHERE nickname = ?", (nickname,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        flash("Nickname not found.")
        return redirect("/login")

    otp_db, expiry = row
    from dateutil import parser  # at the top of your file if not already

    if datetime.utcnow() > parser.parse(expiry):

        flash("❌ OTP expired.")
        return redirect("/login")

    if otp_entered != otp_db:
        flash("❌ Incorrect OTP.")
        return redirect("/verify_otp")

    session["nickname"] = nickname
    session.pop("pending_nickname", None)
    flash(f"✅ Welcome, {nickname}!")
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect("/login")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
