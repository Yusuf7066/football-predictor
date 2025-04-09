from flask import request, redirect, flash, render_template
import sqlite3
import requests
from datetime import datetime, timedelta
from collections import defaultdict

def register_leaderboard_routes(app, headers, RESULTS_URL):

    def get_week(date_str):
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.isocalendar()[1]  # ISO week number

    @app.route("/check_results")
    def check_results():
        response = requests.get(RESULTS_URL, headers=headers)
        if response.status_code != 200:
            return "Error fetching results"

        results = response.json().get("matches", [])
        conn = sqlite3.connect("predictions.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                user TEXT,
                points INTEGER DEFAULT 0,
                week INTEGER,
                PRIMARY KEY (user, week)
            )
        """)

        for match in results:
            match_id = str(match['id'])
            date = match['utcDate'][:10]
            week = get_week(date)
            score = match['score']
            if not score or not score['fullTime']:
                continue

            home_score = score['fullTime'].get('home')
            away_score = score['fullTime'].get('away')
            if home_score is None or away_score is None:
                continue

            if home_score > away_score:
                actual_result = "Home Win"
            elif home_score < away_score:
                actual_result = "Away Win"
            else:
                actual_result = "Draw"

            final_score = f"{home_score}-{away_score}"

            cursor.execute("SELECT user, prediction_type, predicted_score FROM predictions WHERE match_id = ?", (match_id,))
            predictions = cursor.fetchall()

            for user, predicted_type, predicted_score in predictions:
                points = 0
                if predicted_type == actual_result:
                    points += 1
                if predicted_score == final_score:
                    points += 2

                if points > 0:
                    cursor.execute("SELECT points FROM leaderboard WHERE user = ? AND week = ?", (user, week))
                    row = cursor.fetchone()
                    if row:
                        cursor.execute("UPDATE leaderboard SET points = points + ? WHERE user = ? AND week = ?", (points, user, week))
                    else:
                        cursor.execute("INSERT INTO leaderboard (user, points, week) VALUES (?, ?, ?)", (user, points, week))

        conn.commit()
        conn.close()
        flash("✅ Results checked and leaderboard updated!")
        return redirect("/leaderboard")

    @app.route("/leaderboard")
    def leaderboard():
        week = request.args.get("week")

        conn = sqlite3.connect("predictions.db")
        cursor = conn.cursor()
        if week:
            cursor.execute("SELECT user, points FROM leaderboard WHERE week = ? ORDER BY points DESC", (week,))
        else:
            cursor.execute("SELECT user, SUM(points) as total FROM leaderboard GROUP BY user ORDER BY total DESC")

        rows = cursor.fetchall()

        leaderboard_data = []
        top_score = rows[0][1] if rows else 0

        for user, points in rows:
            badges = ""
            if points == top_score:
                badges += "🥇"

            # 🔥 Hot Streak badge logic
            cursor.execute("""
                SELECT prediction_type, predicted_score, match_id FROM predictions
                WHERE user = ? ORDER BY created_at DESC LIMIT 3
            """, (user,))
            recent = cursor.fetchall()
            streak = 0
            for pred_type, pred_score, mid in recent:
                cursor.execute("SELECT score FROM matches WHERE id = ?", (mid,))
                match_score = cursor.fetchone()
                if match_score:
                    home, away = map(int, match_score[0].split("-"))
                    actual = "Draw" if home == away else ("Home Win" if home > away else "Away Win")
                    if pred_type == actual:
                        streak += 1
                    else:
                        break
            if streak == 3:
                badges += "🔥"

            # 🐙 Perfect Score badge
            cursor.execute("""
                SELECT COUNT(*) FROM predictions p
                JOIN matches m ON p.match_id = m.id
                WHERE p.user = ? AND p.predicted_score = m.score
            """, (user,))
            perfect_count = cursor.fetchone()[0]
            if perfect_count:
                badges += "🐙"

            leaderboard_data.append({"user": user, "points": points, "badges": badges})

        conn.close()
        return render_template("leaderboard.html", leaderboard=leaderboard_data, selected_week=week)
