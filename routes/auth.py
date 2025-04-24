# routes/auth.py

from flask import request, redirect, render_template, session, flash
import sqlite3
from datetime import datetime, timedelta
import random
from dateutil import parser
import re

def register_auth_routes(app, client, FROM_WA):

    def is_valid_phone(phone):
        return re.fullmatch(r"(?:\+|00)?[0-9]{10,15}", phone) is not None

    def clean_expired_otps():
        with sqlite3.connect("predictions.db") as conn:
            cursor = conn.cursor()
            # ✅ Ensure resend_count column exists
            cursor.execute("PRAGMA table_info(otp_sessions)")
            columns = [col[1] for col in cursor.fetchall()]
            if "resend_count" not in columns:
                cursor.execute("ALTER TABLE otp_sessions ADD COLUMN resend_count INTEGER DEFAULT 0")
                conn.commit()
                print("✅ resend_count column added dynamically.")
            cursor.execute("DELETE FROM otp_sessions WHERE expires_at < ?", (datetime.utcnow().isoformat(),))
            conn.commit()

    @app.route("/login", methods=["GET", "POST"])
    def login():
        clean_expired_otps()

        if request.method == "POST":
            nickname = request.form.get("nickname")
            phone = request.form.get("phone")

            print("🔐 Login form submitted!")
            print("Nickname:", nickname)
            print("Phone:", phone)

            if not nickname or not phone:
                flash("Name and WhatsApp number are required.")
                return redirect("/login")

            if not is_valid_phone(phone):
                flash("❌ Invalid phone number format.")
                return redirect("/login")

            otp = str(random.randint(100000, 999999))
            expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

            # Store OTP session in DB
            with sqlite3.connect("predictions.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS otp_sessions (
                        nickname TEXT PRIMARY KEY,
                        phone_number TEXT,
                        otp TEXT,
                        expires_at TEXT,
                        resend_count INTEGER DEFAULT 0
                    )
                """)
                cursor.execute("""
                    INSERT OR REPLACE INTO otp_sessions (nickname, phone_number, otp, expires_at, resend_count)
                    VALUES (?, ?, ?, ?, 0)
                """, (nickname, phone, otp, expires_at))
                conn.commit()

            # Try sending the OTP
            try:
                print("➡️ Attempting to send WhatsApp OTP to", phone)
                client.messages.create(
                    from_=FROM_WA,
                    body=f"Your OTP is: {otp} (valid for 5 minutes)",
                    to=f"whatsapp:{phone}"
                )
                flash("📨 OTP sent via WhatsApp!")
                print("✅ OTP sent successfully.")
            except Exception as e:
                print("❌ OTP send failed:", e)
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

            with sqlite3.connect("predictions.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT otp, expires_at FROM otp_sessions WHERE nickname = ?", (nickname,))
                row = cursor.fetchone()

            if not row:
                flash("Session expired or nickname not found.")
                print("❌ OTP session not found for:", nickname)
                return redirect("/login")

            otp_db, expiry = row

            if datetime.utcnow() > parser.parse(expiry):
                flash("❌ OTP expired.")
                return redirect("/login")

            if otp_entered != otp_db:
                flash("❌ Incorrect OTP.")
                print("❌ Incorrect OTP entered for:", nickname)
                return redirect("/verify_otp")

            session["nickname"] = nickname
            flash("✅ Logged in successfully!")
            return redirect("/")

        nickname = session.get("nickname", "")
        return render_template("verify_otp.html", nickname=nickname)


    @app.route("/resend_otp", methods=["POST"])
    def resend_otp():
        nickname = request.form.get("nickname")
        print("🔁 Resend OTP requested for:", nickname)

        with sqlite3.connect("predictions.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone_number, resend_count FROM otp_sessions WHERE nickname = ?", (nickname,))
            row = cursor.fetchone()

            if not row:
                flash("Nickname not found. Please login again.")
                print("❌ Nickname not found in DB.")
                return redirect("/login")

            phone, resend_count = row

            if resend_count >= 3:
                flash("❌ OTP resend limit reached. Please wait before trying again.")
                return redirect("/verify_otp")

            otp = str(random.randint(100000, 999999))
            expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

            cursor.execute("""
                UPDATE otp_sessions
                SET otp = ?, expires_at = ?, resend_count = resend_count + 1
                WHERE nickname = ?
            """, (otp, expires_at, nickname))
            conn.commit()

        try:
            print("📲 Sending WhatsApp OTP to", phone)
            client.messages.create(
                from_=FROM_WA,
                body=f"Your new OTP is: {otp} (valid for 5 minutes)",
                to=f"whatsapp:{phone}"
            )
            flash("📨 New OTP sent via WhatsApp!")
            print("✅ New OTP sent successfully.")
        except Exception as e:
            flash(f"❌ Failed to send OTP: {e}")
            print("❌ Failed to send new OTP:", e)

        session["nickname"] = nickname
        return redirect("/verify_otp")


    @app.route("/logout")
    def logout():
        session.clear()
        flash("🔓 Logged out successfully.")
        return redirect("/login")
