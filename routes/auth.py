from flask import request, redirect, render_template, session, flash
import sqlite3
import random
from datetime import datetime, timedelta

def register_auth_routes(app, client, FROM_WA):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            nickname = request.form.get("nickname")
            phone = request.form.get("phone")
            if not nickname or not phone:
                flash("Name and WhatsApp number are required.")
                return redirect("/login")

            otp = str(random.randint(100000, 999999))
            expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

            conn = sqlite3.connect("predictions.db")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otp_sessions (
                    nickname TEXT PRIMARY KEY,
                    phone_number TEXT,
                    otp TEXT,
                    expires_at TEXT
                )
            """)
            cursor.execute("""
                INSERT OR REPLACE INTO otp_sessions (nickname, phone_number, otp, expires_at)
                VALUES (?, ?, ?, ?)
            """, (nickname, phone, otp, expires_at))
            conn.commit()
            conn.close()

            try:
                client.messages.create(
                    from_=FROM_WA,
                    body=f"Your OTP is: {otp}",
                    to=f"whatsapp:{phone}"
                )
                flash("OTP sent via WhatsApp.")
            except Exception as e:
                flash(f"Failed to send OTP: {e}")
                return redirect("/login")

            session["nickname"] = nickname
            return redirect("/verify_otp")

        return render_template("login.html")

    @app.route("/verify_otp", methods=["GET", "POST"])
    def verify_otp():
        nickname = session.get("nickname", "")
        if request.method == "POST":
            otp_input = request.form.get("otp")
            conn = sqlite3.connect("predictions.db")
            cursor = conn.cursor()
            cursor.execute("SELECT otp, expires_at FROM otp_sessions WHERE nickname = ?", (nickname,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                flash("Nickname not found.")
                return redirect("/login")

            otp, expires = row
            if datetime.utcnow() > datetime.fromisoformat(expires):
                flash("OTP expired.")
                return redirect("/login")

            if otp_input != otp:
                flash("Incorrect OTP.")
                return redirect("/verify_otp")

            session["nickname"] = nickname
            flash("Logged in successfully!")
            return redirect("/")

        return render_template("verify_otp.html", nickname=nickname)

    @app.route("/logout")
    def logout():
        session.clear()
        flash("Logged out.")
        return redirect("/login")
