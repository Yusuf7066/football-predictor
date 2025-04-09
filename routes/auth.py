# routes/auth.py

from flask import request, redirect, render_template, session, flash
import sqlite3
from datetime import datetime, timedelta
import random
from dateutil import parser

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
                    body=f"Your OTP is: {otp} (valid for 5 minutes)",
                    to=f"whatsapp:{phone}"
                )
                flash("📨 OTP sent via WhatsApp!")
            except Exception as e:
                flash(f"❌ Failed to send OTP: {e}")
                return redirect("/login")

            session["nickname"] = nickname
            return redirect("/verify_otp")

        return render_template("login.html")


    @app.route("/verify_otp", methods=["GET", "POST"])
    def verify_otp():
        if request.method == "POST":
            nickname = request.form.get("nickname")
            otp_entered = request.form.get("otp")

            conn = sqlite3.connect("predictions.db")
            cursor = conn.cursor()
            cursor.execute("SELECT otp, expires_at FROM otp_sessions WHERE nickname = ?", (nickname,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                flash("Session expired or nickname not found.")
                return redirect("/login")

            otp_db, expiry = row

            if datetime.utcnow() > parser.parse(expiry):
                flash("❌ OTP expired.")
                return redirect("/login")

            if otp_entered != otp_db:
                flash("❌ Incorrect OTP.")
                return redirect("/verify_otp")

            session["nickname"] = nickname
            flash("✅ Logged in successfully!")
            return redirect("/")

        nickname = session.get("nickname", "")
        return render_template("verify_otp.html", nickname=nickname)


    @app.route("/resend_otp", methods=["POST"])
    def resend_otp():
        nickname = request.form.get("nickname")

        conn = sqlite3.connect("predictions.db")
        cursor = conn.cursor()
        cursor.execute("SELECT phone_number FROM otp_sessions WHERE nickname = ?", (nickname,))
        row = cursor.fetchone()

        if not row:
            flash("Nickname not found. Please login again.")
            conn.close()
            return redirect("/login")

        phone = row[0]
        otp = str(random.randint(100000, 999999))
        expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

        cursor.execute("UPDATE otp_sessions SET otp = ?, expires_at = ? WHERE nickname = ?", (otp, expires_at, nickname))
        conn.commit()
        conn.close()

        try:
            client.messages.create(
                from_=FROM_WA,
                body=f"Your new OTP is: {otp} (valid for 5 minutes)",
                to=f"whatsapp:{phone}"
            )
            flash("📨 New OTP sent via WhatsApp!")
        except Exception as e:
            flash(f"❌ Failed to send OTP: {e}")

        session["nickname"] = nickname
        return redirect("/verify_otp")
