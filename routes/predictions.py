from flask import request, render_template, session, redirect, flash
from datetime import datetime, timedelta
import sqlite3
import requests

def register_prediction_routes(app, headers):
    MATCHES_URL = "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"
    STANDINGS_URL = "https://api.football-data.org/v4/competitions/PL/standings"

    def normalize(name):
        return name.lower().replace(" fc", "").replace(".", "").strip()

    def get_team_rankings():
        r = requests.get(STANDINGS_URL, headers=headers)
        data = r.json()
        standings = {}
        for team in data['standings'][0]['table']:
            standings[normalize(team['team']['name'])] = team['position']
        return standings

    def get_matches():
        r = requests.get(MATCHES_URL, headers=headers)
        data = r.json().get("matches", [])
        rankings = get_team_rankings()
        matches = []
        for match in data:
            home = match['homeTeam']['name']
            away = match['awayTeam']['name']
            home_norm = normalize(home)
            away_norm = normalize(away)
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
            matches.append({
                "match_id": match['id'],
                "home": home,
                "away": away,
                "date": match['utcDate'][:10],
                "utc_datetime": match['utcDate'],
                "prediction": prediction
            })
        return matches

    @app.route("/")
    def home():
        if "nickname" not in session:
            flash("Please log in to predict.")
            return redirect("/login")
        return render_template("index.html", matches=get_matches(), utcnow=datetime.utcnow())

    @app.route("/predict", methods=["POST"])
    def submit_prediction():
        match_id = request.form.get("match_id")
        prediction = request.form.get("prediction")
        home_score = request.form.get("home_score")
        away_score = request.form.get("away_score")
        match_time = request.form.get("match_time")
        user = session.get("nickname")
        ip = request.remote_addr

        if datetime.utcnow() >= datetime.strptime(match_time, "%Y-%m-%dT%H:%M:%SZ") - timedelta(minutes=2):
            flash("⏱️ Prediction closed.")
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
            flash("❗ Score doesn’t match outcome.")
            return redirect("/")

        score = f"{home}-{away}"

        conn = sqlite3.connect("predictions.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                match_id TEXT,
                prediction_type TEXT,
                predicted_score TEXT,
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("SELECT 1 FROM predictions WHERE match_id = ? AND (user = ? OR ip_address = ?)",
                       (match_id, user, ip))
        if cursor.fetchone():
            flash("Already submitted.")
            return redirect("/")
        cursor.execute("INSERT INTO predictions (user, match_id, prediction_type, predicted_score, ip_address) VALUES (?, ?, ?, ?, ?)",
                       (user, match_id, prediction, score, ip))
        conn.commit()
        conn.close()

        flash("✅ Prediction saved.")
        return redirect("/")
