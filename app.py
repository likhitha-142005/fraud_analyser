from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session, flash)
import pandas as pd
import os, sys, json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config
from database import (
    init_db,
    get_user_by_username, get_user_by_email,
    create_user, update_last_login, log_failed_login,
    get_user_stats, get_all_users,
    get_db_stats, get_transaction_count_by_user, get_recent_login_logs,
    load_transactions_from_db, insert_transaction, insert_alert,
)
from modules.risk_scorer    import compute_risk_score, score_dataframe
from modules.alert_system   import generate_alert
from modules.fraud_detector import predict_single

app = Flask(__name__)
app.config.from_object(Config)
init_db()


# ── Helpers ────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

def load_csv_data():
    path = Config.SCORED_PATH if os.path.exists(Config.SCORED_PATH) else Config.DATA_PATH
    df   = pd.read_csv(path)
    if "risk_score" not in df.columns:
        df = score_dataframe(df)
    return df

def get_stats():
    stats = get_db_stats()
    if stats and int(stats.get("total") or 0) > 0:
        return {k: (int(v) if v is not None else 0) for k, v in stats.items()}
    df = load_csv_data()
    return {
        "total":    len(df),
        "fraud":    int(df["is_fraud"].sum()),
        "critical": int((df["risk_level"] == "CRITICAL").sum()) if "risk_level" in df else 0,
        "high":     int((df["risk_level"] == "HIGH").sum())     if "risk_level" in df else 0,
        "medium":   int((df["risk_level"] == "MEDIUM").sum())   if "risk_level" in df else 0,
        "low":      int((df["risk_level"] == "LOW").sum())      if "risk_level" in df else 0,
        "avg_risk": round(float(df["risk_score"].mean()), 2)    if "risk_score" in df else 0,
        "total_users": 0,
    }

def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


# ── Register ───────────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect(url_for("dashboard"))

    errors, form = {}, {}
    if request.method == "POST":
        form = {
            "full_name": request.form.get("full_name", "").strip(),
            "username":  request.form.get("username",  "").strip().lower(),
            "email":     request.form.get("email",     "").strip().lower(),
            "password":  request.form.get("password",  ""),
            "confirm":   request.form.get("confirm",   ""),
        }
        # ── Validate ──
        if len(form["full_name"]) < 2:
            errors["full_name"] = "Full name is required (min 2 chars)."
        if len(form["username"]) < 3:
            errors["username"] = "Username must be at least 3 characters."
        elif not form["username"].isalnum():
            errors["username"] = "Username can only contain letters and numbers."
        if "@" not in form["email"] or "." not in form["email"].split("@")[-1]:
            errors["email"] = "Enter a valid email address."
        if len(form["password"]) < 6:
            errors["password"] = "Password must be at least 6 characters."
        if form["password"] != form["confirm"]:
            errors["confirm"] = "Passwords do not match."

        if not errors:
            if get_user_by_username(form["username"]):
                errors["username"] = "Username already taken. Choose another."
            elif get_user_by_email(form["email"]):
                errors["email"] = "Email is already registered. Try logging in."
            else:
                hashed = generate_password_hash(form["password"])
                ok = create_user(
                    form["full_name"], form["username"],
                    form["email"], hashed, role="analyst"
                )
                if ok:
                    flash(f"Account created for {form['full_name']}! Please login.", "success")
                    return redirect(url_for("login"))
                else:
                    errors["general"] = "Registration failed. Please try again."

    return render_template("register.html", errors=errors, form=form)


# ── Login ──────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        ip       = client_ip()

        user = get_user_by_username(username)

        if user and check_password_hash(user["password_hash"], password):
            session["user"]        = user["username"]
            session["full_name"]   = user["full_name"]
            session["role"]        = user["role"]
            session["user_id"]     = user["id"]
            update_last_login(username, ip)
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            log_failed_login(username, ip)
            error = "Invalid username or password. Please try again."

    return render_template("index.html", error=error)


# ── Logout ─────────────────────────────────────────────────────────────────────
@app.route("/logout")
def logout():
    name = session.get("full_name", "User")
    session.clear()
    flash(f"Goodbye, {name}! You've been logged out.", "info")
    return redirect(url_for("login"))


# ── Dashboard ──────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    stats      = get_stats()
    user_stats = get_user_stats(session["user"])
    rows       = load_transactions_from_db(limit=10)
    recent     = rows if rows else load_csv_data().tail(10).to_dict(orient="records")
    txn_by_user = get_transaction_count_by_user()
    return render_template("dashboard.html",
        stats=stats, recent=recent,
        user_stats=user_stats, txn_by_user=txn_by_user)


# ── Transactions ───────────────────────────────────────────────────────────────
@app.route("/transactions")
@login_required
def transactions():
    page     = int(request.args.get("page", 1))
    per_page = 20
    level    = request.args.get("level", "")
    rows     = load_transactions_from_db(limit=2000, level=level or None)
    if not rows:
        rows = load_csv_data().to_dict(orient="records")
    total       = len(rows)
    start       = (page - 1) * per_page
    records     = rows[start: start + per_page]
    total_pages = (total // per_page) + 1
    return render_template("transaction.html",
        transactions=records, page=page,
        total_pages=total_pages, total=total)


# ── Transaction detail ─────────────────────────────────────────────────────────
@app.route("/transaction/<txn_id>")
@login_required
def transaction_detail(txn_id):
    rows = load_transactions_from_db(limit=10000)
    txn  = next((r for r in rows if str(r.get("transaction_id")) == txn_id), None)
    if not txn:
        df  = load_csv_data()
        row = df[df["transaction_id"] == txn_id]
        if row.empty:
            return "Transaction not found", 404
        txn = row.iloc[0].to_dict()
    risk_result = compute_risk_score(txn)
    alert       = generate_alert(txn, risk_result)
    return render_template("transaction_detail.html",
        txn=txn, risk=risk_result, alert=alert)


# ── Analyse ────────────────────────────────────────────────────────────────────
@app.route("/analyse", methods=["GET", "POST"])
@login_required
def analyse():
    result = None
    if request.method == "POST":
        txn = {
            "transaction_id":    f"LIVE-{datetime.now().strftime('%H%M%S')}",
            "amount":            float(request.form.get("amount", 0)),
            "merchant":          request.form.get("merchant", "Unknown"),
            "location":          request.form.get("location", "Unknown"),
            "device":            request.form.get("device", "Unknown"),
            "payment_method":    request.form.get("payment_method", "UPI"),
            "hour_of_day":       int(request.form.get("hour_of_day", 12)),
            "day_of_week":       datetime.now().weekday(),
            "failed_attempts":   int(request.form.get("failed_attempts", 0)),
            "txn_velocity":      int(request.form.get("txn_velocity", 1)),
            "account_age_days":  int(request.form.get("account_age_days", 365)),
            "avg_user_amount":   float(request.form.get("avg_user_amount", 1000)),
            "is_foreign_location": 1 if request.form.get("location") in
                ["Dubai","Singapore","London","USA","Malaysia","Thailand",
                 "Hong Kong","Canada","Australia","Unknown_Location"] else 0,
            "is_unusual_device": int(bool(request.form.get("is_unusual_device"))),
            "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        txn["amount_deviation"]   = round(txn["amount"] / max(txn["avg_user_amount"], 1), 4)
        risk_result               = compute_risk_score(txn)
        ml_result                 = predict_single(txn)
        alert                     = generate_alert(txn, risk_result)
        txn["risk_score"]         = risk_result["risk_score"]
        txn["risk_level"]         = risk_result["risk_level"]
        txn["recommended_action"] = risk_result["recommended_action"]
        txn["is_fraud"]           = ml_result["is_fraud_predicted"]

        # Save to DB with analyst name
        insert_transaction(txn, analysed_by=session.get("user", ""))
        insert_alert(alert)

        result = {"txn": txn, "risk": risk_result, "ml": ml_result, "alert": alert}

    recent_txns = load_transactions_from_db(limit=50)
    if not recent_txns:
        recent_txns = load_csv_data().tail(50).to_dict(orient="records")
    return render_template("analyse.html", result=result, recent_txns=recent_txns)


# ── Reports ────────────────────────────────────────────────────────────────────
@app.route("/reports")
@login_required
def reports():
    rows = load_transactions_from_db(limit=5000)
    df   = pd.DataFrame(rows) if rows else load_csv_data()
    df["is_fraud"] = df["is_fraud"].astype(int)
    by_merchant = df.groupby("merchant")["is_fraud"].sum().sort_values(ascending=False).head(10).to_dict()
    by_location = df.groupby("location")["is_fraud"].sum().sort_values(ascending=False).head(10).to_dict()
    by_hour     = df.groupby("hour_of_day")["is_fraud"].sum().to_dict()
    by_method   = df.groupby("payment_method")["is_fraud"].sum().to_dict()
    return render_template("report.html",
        by_merchant=json.dumps(by_merchant),
        by_location=json.dumps(by_location),
        by_hour=json.dumps({str(k): int(v) for k, v in by_hour.items()}),
        by_method=json.dumps(by_method))


# ── Admin: Users page ──────────────────────────────────────────────────────────
@app.route("/admin/users")
@admin_required
def admin_users():
    users      = get_all_users()
    login_logs = get_recent_login_logs(limit=30)
    txn_counts = get_transaction_count_by_user()
    return render_template("admin_users.html",
        users=users, login_logs=login_logs, txn_counts=txn_counts)


# ── API ────────────────────────────────────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())

@app.route("/api/predict", methods=["POST"])
def api_predict():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    risk  = compute_risk_score(data)
    ml    = predict_single(data)
    alert = generate_alert(data, risk)
    return jsonify({
        "risk": risk, "ml": ml,
        "alert": {
            "level":         alert["risk_level"],
            "action":        alert["action"],
            "sms":           alert["sms_message"],
            "email_subject": alert["email_subject"],
        }
    })

@app.route("/api/user/stats")
@login_required
def api_user_stats():
    return jsonify(get_user_stats(session["user"]))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
