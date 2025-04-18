from flask import request, render_template, session, redirect, flash
from datetime import datetime, timedelta
import sqlite3
import requests

def normalize_name(name):
    return name.lower().replace(" fc", "").replace(".", "").strip()

def register_prediction_routes(app, headers):
    MATCHES_URL = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    STANDINGS_URL = "https://api.football-data.org/v4/competitions/PL/standings"

    def normalize(name):
        return name.lower().replace(" fc", "").replace(".", "").strip()

    def get_team_rankings():
        response = requests.get(STANDINGS_URL, headers=headers)
        rankings = {}
        if response.status_code == 200:
            data = response.json()
            if 'standings' in data:
                for team in data['standings'][0]['table']:
                    rankings[normalize_name(team['team']['name'])] = team['position']
            else:
                print("⚠️ 'standings' key missing in response.")
        else:
            print("❌ Failed to fetch standings. Status code:", response.status_code)
        return rankings


    def get_user_predictions():
        user_predictions = set()
        user = session.get("nickname")
        ip = request.remote_addr
        with sqlite3.connect("predictions.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT,
                    match_id TEXT,
                    home_team TEXT,
                    away_team TEXT,
                    match_date TEXT,
                    prediction_type TEXT,
                    predicted_score TEXT,
                    result TEXT DEFAULT '',
                    ip_address TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("SELECT match_id FROM predictions WHERE user = ? OR ip_address = ?", (user, ip))
            for row in cursor.fetchall():
                user_predictions.add(row[0])
        return user_predictions

    def get_matches():
        try:
            r = requests.get(MATCHES_URL, headers=headers)
            data = r.json()
            matches = []

            nickname = session.get("nickname")
            submitted_ids = set()

            # Fetch user's submitted match_ids
            if nickname:
                with sqlite3.connect("predictions.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT match_id FROM predictions WHERE user = ?", (nickname,))
                    submitted_ids = {row[0] for row in cursor.fetchall()}

            for match in data.get("matches", []):
                match_id = str(match["id"])
                utc_datetime = match["utcDate"]
                date = utc_datetime[:10]
                home = match["homeTeam"]["name"]
                away = match["awayTeam"]["name"]
                home_crest = match["homeTeam"]["crest"]
                away_crest = match["awayTeam"]["crest"]

                matches.append({
                    "match_id": match_id,
                    "utc_datetime": utc_datetime,
                    "date": date,
                    "home": home,
                    "away": away,
                    "home_crest": home_crest,
                    "away_crest": away_crest,
                    "user_submitted": match_id in submitted_ids
                })

            return matches
        except Exception as e:
            print("❌ Error in get_matches():", e)
            return []


    @app.route("/")
    def home():
        user = session.get("nickname")
        if not user:
            flash("🔐 Login required to submit predictions.")
            return redirect("/login")
        return render_template("index.html", matches=get_matches(), utcnow=datetime.utcnow())

    @app.route("/predict", methods=["POST"])
    def submit_prediction():
        user = session.get("nickname")
        match_id = request.form.get("match_id")
        prediction = request.form.get("prediction")
        home_score = request.form.get("home_score")
        away_score = request.form.get("away_score")
        match_time = request.form.get("match_time")
        home_team = request.form.get("home_team")
        away_team = request.form.get("away_team")
        match_date = request.form.get("match_date")
        ip = request.remote_addr

        print("🔎 Current session nickname:", user)
        if not match_time:
            flash("Missing match time. Please try again.")
            return redirect("/")

        try:
            if datetime.utcnow() >= datetime.strptime(match_time, "%Y-%m-%dT%H:%M:%SZ") - timedelta(minutes=2):
                flash("Prediction window has closed for this match.")
                return redirect("/")
        except Exception as e:
            print("❌ Error parsing match time:", e)
            flash("Invalid match time.")
            return redirect("/")

        try:
            home = int(home_score)
            away = int(away_score)
            if prediction == "Home Win" and home <= away:
                raise ValueError
            if prediction == "Away Win" and away <= home:
                raise ValueError
            if prediction == "Draw" and home != away:
                raise ValueError
        except:
            flash("⚠️ Score doesn't match your selected outcome.")
            return redirect("/")

        predicted_score = f"{home}-{away}"

        with sqlite3.connect("predictions.db") as conn:
            cursor = conn.cursor()
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

            cursor.execute("SELECT 1 FROM predictions WHERE match_id = ? AND (user = ? OR ip_address = ?)", (match_id, user, ip))
            if cursor.fetchone():
                flash("You already submitted for this match.")
                return redirect("/")

            cursor.execute("""
                INSERT INTO predictions (
                    user, match_id, home_team, away_team, match_date,
                    prediction_type, predicted_score, result, ip_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?)
            """, (user, match_id, home_team, away_team, match_date, prediction, predicted_score, ip))

            conn.commit()

        flash("✅ Your prediction has been saved!")
        return redirect("/")
