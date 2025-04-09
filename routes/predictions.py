from flask import request, redirect, flash, session, render_template
import sqlite3
from datetime import datetime, timedelta
import requests

def register_prediction_routes(app, headers):

    @app.route("/predict", methods=["POST"])
    def submit_prediction():
        match_id = request.form.get("match_id")
        prediction_type = request.form.get("prediction")
        home_score = request.form.get("home_score")
        away_score = request.form.get("away_score")
        match_time = request.form.get("match_time")
        user = session.get("nickname")
        ip_address = request.remote_addr

        if not user:
            flash("Login required to submit prediction.")
            return redirect("/login")

        if datetime.utcnow() >= datetime.strptime(match_time, "%Y-%m-%dT%H:%M:%SZ") - timedelta(minutes=2):
            flash("Prediction window has closed for this match.")
            return redirect("/")

        try:
            home = int(home_score)
            away = int(away_score)
            if prediction_type == "Home Win" and home <= away:
                raise ValueError
            if prediction_type == "Away Win" and away <= home:
                raise ValueError
            if prediction_type == "Draw" and home != away:
                raise ValueError
        except:
            flash("⚠️ Score doesn't match your selected outcome.")
            return redirect("/")

        predicted_score = f"{home}-{away}"

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
        cursor.execute("SELECT 1 FROM predictions WHERE match_id = ? AND (user = ? OR ip_address = ?)", (match_id, user, ip_address))
        if cursor.fetchone():
            flash("You already submitted for this match.")
            conn.close()
            return redirect("/")

        cursor.execute("""
            INSERT INTO predictions (user, match_id, prediction_type, predicted_score, ip_address)
            VALUES (?, ?, ?, ?, ?)
        """, (user, match_id, prediction_type, predicted_score, ip_address))
        conn.commit()
        conn.close()
        flash("✅ Your prediction has been saved!")
        return redirect("/")
