from flask import Blueprint, render_template, request, redirect, flash, session
import sqlite3
import requests
from datetime import datetime, timedelta


def register_prediction_history_route(app, headers):
    MATCH_DETAILS_URL = "https://api.football-data.org/v4/matches/{}"

    def fetch_match_info(match_id):
        try:
            r = requests.get(MATCH_DETAILS_URL.format(match_id), headers=headers)
            data = r.json()
            print("📦 Match API Data:", data)

            home = data['homeTeam']['name']
            away = data['awayTeam']['name']
            home_crest = data['homeTeam']['crest']
            away_crest = data['awayTeam']['crest']
            date = data['utcDate'][:10]
            full_time = data['score']['fullTime']
            home_goals = full_time.get('home')
            away_goals = full_time.get('away')
            winner = data['score']['winner']

            result_type = ""
            if winner == "HOME_TEAM":
                result_type = "Home Win"
            elif winner == "AWAY_TEAM":
                result_type = "Away Win"
            elif winner == "DRAW":
                result_type = "Draw"

            return {
                "home": home,
                "away": away,
                "home_crest": home_crest,
                "away_crest": away_crest,
                "date": date,
                "result_type": result_type,
                "score": f"{home_goals}-{away_goals}" if home_goals is not None and away_goals is not None else None
            }
        except Exception as e:
            print("❌ Error fetching match info:", e)
            return None

    @app.route("/my_predictions")
    def my_predictions():
        nickname = session.get("nickname")
        print("📋 Logged in as:", nickname)
        if not nickname:
            flash("🔐 Please log in to view your predictions.")
            return redirect("/login")

        week_filter = request.args.get("week")

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

            query = """
                SELECT match_id, home_team, away_team, match_date, prediction_type, predicted_score, result
                FROM predictions
                WHERE user = ?
            """
            params = [nickname]

            if week_filter:
                query += " AND strftime('%W', match_date) = ?"
                params.append(week_filter)

            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

        predictions = []
        for row in rows:
            match_id, home, away, date, predicted_type, predicted_score, result = row

            if not result or not home or not away:
                info = fetch_match_info(match_id)
                if info:
                    if info['result_type']:
                        result = info['result_type']
                        with sqlite3.connect("predictions.db") as conn:
                            c = conn.cursor()
                            c.execute("UPDATE predictions SET result = ? WHERE match_id = ? AND user = ?", (result, match_id, nickname))
                            conn.commit()
                        print(f"✅ Updated result for match {match_id}: {result}")
                    if not home or not away:
                        home = info['home']
                        away = info['away']
                        date = info['date']

            info = fetch_match_info(match_id)
            home_crest = info['home_crest'] if info else ""
            away_crest = info['away_crest'] if info else ""
            final_score = info['score'] if info and info['score'] else "TBD"

            predictions.append({
                "match_id": match_id,
                "date": date or "Unknown",
                "home": home or "Unknown",
                "away": away or "Unknown",
                "home_crest": home_crest,
                "away_crest": away_crest,
                "prediction_type": predicted_type,
                "predicted_score": predicted_score,
                "final_score": final_score,
                "result": result,
                "status": "✅ Correct" if result == predicted_type else ("❌ Wrong" if result else "⏳ Pending")
            })

        return render_template("my_predictions.html", predictions=predictions, selected_week=week_filter)

def register_edit_prediction_route(app):
    @app.route("/edit_prediction/<match_id>", methods=["GET", "POST"])
    def edit_prediction(match_id):
        user = session.get("nickname")
        if not user:
            flash("🔐 Please log in to edit your prediction.")
            return redirect("/login")

        if request.method == "POST":
            prediction = request.form.get("prediction")
            home_score = request.form.get("home_score")
            away_score = request.form.get("away_score")
            match_time = request.form.get("match_time")

            if datetime.utcnow() >= datetime.strptime(match_time, "%Y-%m-%dT%H:%M:%SZ") - timedelta(minutes=2):
                flash("❌ Cannot edit prediction. Match is starting soon or already started.")
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
                return redirect(request.url)

            predicted_score = f"{home}-{away}"

            with sqlite3.connect("predictions.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE predictions
                    SET prediction_type = ?, predicted_score = ?
                    WHERE match_id = ? AND user = ?
                """, (prediction, predicted_score, match_id, user))
                conn.commit()

            flash("✅ Prediction updated!")
            return redirect("/my_predictions")

        with sqlite3.connect("predictions.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prediction_type, predicted_score, match_date, home_team, away_team
                FROM predictions
                WHERE match_id = ? AND user = ?
            """, (match_id, user))
            row = cursor.fetchone()

        if not row:
            flash("❌ No prediction found to edit.")
            return redirect("/my_predictions")

        prediction_type, predicted_score, match_date, home_team, away_team = row
        home_score, away_score = predicted_score.split("-")

        return render_template("edit_prediction.html", match_id=match_id, prediction_type=prediction_type,
                               home_score=home_score, away_score=away_score,
                               match_date=match_date, home_team=home_team, away_team=away_team)
