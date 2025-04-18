from flask import request, redirect, flash, render_template
import sqlite3
import requests
from datetime import datetime


def register_leaderboard_routes(app, headers, RESULTS_URL):

    def get_week(date_str):
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.isocalendar()[1]  # ISO week number

    @app.route("/leaderboard")
    def leaderboard():
        week = request.args.get("week")
        conn = sqlite3.connect("predictions.db")
        cursor = conn.cursor()

        # Get distinct weeks
        cursor.execute("SELECT DISTINCT strftime('%W', match_date) as week FROM predictions WHERE match_date IS NOT NULL")
        weeks = sorted([int(w[0]) for w in cursor.fetchall() if w[0].isdigit()])

        query = """
            SELECT user,
                   COUNT(*) as total_predictions,
                   SUM(CASE WHEN result = prediction_type THEN 1 ELSE 0 END) as correct_predictions,
                   SUM(CASE WHEN result = prediction_type THEN 1 ELSE 0 END) + 
                   SUM(CASE WHEN predicted_score = result AND result != '' THEN 2 ELSE 0 END) as points
            FROM predictions
            WHERE user IS NOT NULL
        """
        params = []
        if week:
            query += " AND strftime('%W', match_date) = ?"
            params.append(str(week).zfill(2))
        query += " GROUP BY user ORDER BY points DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        leaderboard_data = []
        top_score = rows[0][3] if rows else 0

        for row in rows:
            user, total, correct, points = row
            badges = []
            if points == top_score:
                badges.append("🥇")

            # 🔥 Hot Streak
            cursor.execute("""
                SELECT prediction_type, match_id FROM predictions
                WHERE user = ? AND result != ''
                ORDER BY created_at DESC LIMIT 3
            """, (user,))
            streak_rows = cursor.fetchall()
            streak = len(streak_rows) == 3 and all(
                pred == cursor.execute("SELECT result FROM predictions WHERE match_id = ? AND user = ?",
                                       (mid, user)).fetchone()[0] for pred, mid in streak_rows)
            if streak:
                badges.append("🔥")

            # 🐙 Perfect Score
            cursor.execute("""
                SELECT COUNT(*) FROM predictions
                WHERE user = ? AND predicted_score = result AND result != ''
            """, (user,))
            if cursor.fetchone()[0]:
                badges.append("🐙")

            leaderboard_data.append({
                "user": user,
                "total_predictions": total,
                "correct_predictions": correct or 0,
                "points": points or 0,
                "badges": badges
            })

        conn.close()
        return render_template("leaderboard.html", leaderboard=leaderboard_data, weeks=weeks,
                               selected_week=int(week) if week else None)

    @app.route("/check_results")
    def check_results():
        response = requests.get(RESULTS_URL, headers=headers)
        if response.status_code != 200:
            return "Error fetching results"

        results = response.json().get("matches", [])
        conn = sqlite3.connect("predictions.db")
        cursor = conn.cursor()

        for match in results:
            match_id = str(match['id'])
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
            cursor.execute("""
                UPDATE predictions
                SET result = ?
                WHERE match_id = ?
            """, (actual_result, match_id))

        conn.commit()
        conn.close()
        flash("✅ Results checked and predictions updated!")
        return redirect("/leaderboard")
