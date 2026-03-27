# modules/risk_scorer.py
import pandas as pd
import numpy as np

# ── Location tiers ─────────────────────────────────────────────────────────────
DOMESTIC = [
    "Hyderabad","Mumbai","Delhi","Bangalore","Chennai",
    "Kolkata","Pune","Ahmedabad","Jaipur","Surat",
    "Kochi","Lucknow","Bhopal","Indore","Nagpur"
]
INTL_LOW  = ["Germany","France","Japan","South Korea","Netherlands","Switzerland"]
INTL_MED  = ["Dubai","Singapore","London","USA","Malaysia","Thailand","Hong Kong","Canada","Australia"]
INTL_HIGH = ["Unknown_Location","Unknown","None","unknown_location"]

AMOUNT_TIERS = [
    (200000, 1.00, "Extremely high amount"),
    (100000, 0.85, "Very high amount"),
    (50000,  0.65, "High amount"),
    (20000,  0.35, "Above average amount"),
    (10000,  0.15, "Moderately high amount"),
]

WEIGHTS = {
    "location":   17,
    "amount_abs": 10,
    "amount_dev": 20,
    "velocity":   18,
    "failed":     15,
    "device":      8,
    "hour":        7,
    "account":     5,
}

RISK_LEVELS = [
    ("CRITICAL", 80, 101),
    ("HIGH",     60,  80),
    ("MEDIUM",   30,  60),
    ("LOW",       0,  30),
]

ACTION_MAP = {
    "LOW": "APPROVE", "MEDIUM": "REVIEW",
    "HIGH": "HOLD & VERIFY", "CRITICAL": "BLOCK"
}


def _location_score(location, home=""):
    loc = str(location).strip()
    if loc in DOMESTIC:
        if home and loc != home:
            return 0.15, f"Transaction from different city: {loc}"
        return 0.0, ""
    if loc in INTL_LOW:
        return 0.30, f"Low-risk international location: {loc}"
    if loc in INTL_MED:
        return 0.75, f"International transaction: {loc}"
    if loc in INTL_HIGH:
        return 1.00, "Unknown / unrecognised location"
    return 0.85, f"Unrecognised location: {loc}"


def _amount_score(amount, avg):
    contrib, reasons = 0.0, []

    # Absolute tier
    for threshold, weight, label in AMOUNT_TIERS:
        if amount >= threshold:
            contrib = max(contrib, weight)
            reasons.append(f"{label}: ₹{amount:,.0f}")
            break

    # Deviation from user average
    if avg and avg > 0:
        dev = amount / avg
        if dev >= 20:
            contrib = max(contrib, 1.0)
            reasons.append(f"Amount is {dev:.0f}x your usual (avg ₹{avg:,.0f}) — extremely unusual")
        elif dev >= 10:
            contrib = max(contrib, 0.85)
            reasons.append(f"Amount is {dev:.0f}x your usual spending")
        elif dev >= 5:
            contrib = max(contrib, 0.60)
            reasons.append(f"Amount is {dev:.1f}x your usual spending")
        elif dev >= 3:
            contrib = max(contrib, 0.30)
            reasons.append(f"Amount is {dev:.1f}x above your average")

    return contrib, reasons


def compute_risk_score(row: dict) -> dict:
    score   = 0.0
    factors = []
    breakdown = {}

    amount  = float(row.get("amount", 0))
    avg     = float(row.get("avg_user_amount", 1000))
    loc     = str(row.get("location", ""))
    home    = str(row.get("home_location", ""))
    vel     = int(row.get("txn_velocity", 1))
    fails   = int(row.get("failed_attempts", 0))
    hour    = int(row.get("hour_of_day", 12))
    age     = int(row.get("account_age_days", 365))
    unusual = int(row.get("is_unusual_device", 0))

    # 1. Location
    lc, lr = _location_score(loc, home)
    s = WEIGHTS["location"] * lc
    score += s; breakdown["location"] = round(s, 1)
    if lr: factors.append(lr)

    # 2. Amount absolute + deviation
    ac, ar = _amount_score(amount, avg)
    s_abs = WEIGHTS["amount_abs"] * ac
    s_dev = WEIGHTS["amount_dev"] * min((amount / max(avg,1)) / 20, 1.0)
    score += s_abs + s_dev
    breakdown["amount"] = round(s_abs + s_dev, 1)
    factors.extend(ar)

    # 3. Velocity
    if vel >= 15:
        s = WEIGHTS["velocity"] * 1.0
        factors.append(f"Very high velocity: {vel} txns/hr — possible card testing")
    elif vel >= 8:
        s = WEIGHTS["velocity"] * 0.7
        factors.append(f"High velocity: {vel} transactions in last hour")
    elif vel >= 5:
        s = WEIGHTS["velocity"] * 0.4
        factors.append(f"Moderate velocity: {vel} transactions in last hour")
    else:
        s = 0
    score += s; breakdown["velocity"] = round(s, 1)

    # 4. Failed attempts
    if fails >= 5:
        s = WEIGHTS["failed"] * 1.0
        factors.append(f"{fails} failed attempts — possible brute force")
    elif fails >= 3:
        s = WEIGHTS["failed"] * 0.8
        factors.append(f"{fails} failed attempts before this transaction")
    elif fails >= 1:
        s = WEIGHTS["failed"] * 0.3
        factors.append(f"{fails} failed attempt(s) before this transaction")
    else:
        s = 0
    score += s; breakdown["failed"] = round(s, 1)

    # 5. Unusual device
    s = WEIGHTS["device"] * unusual
    if unusual:
        factors.append(f"Unrecognised device used: {row.get('device','?')}")
    score += s; breakdown["device"] = round(s, 1)

    # 6. Odd hour
    if 0 <= hour <= 4:
        s = WEIGHTS["hour"] * 1.0
        factors.append(f"Late-night transaction at {hour:02d}:00 AM")
    elif hour >= 23:
        s = WEIGHTS["hour"] * 0.7
        factors.append(f"Late-night transaction at {hour:02d}:00")
    else:
        s = 0
    score += s; breakdown["hour"] = round(s, 1)

    # 7. New account
    if age < 7:
        s = WEIGHTS["account"] * 1.0
        factors.append(f"Very new account: only {age} days old")
    elif age < 30:
        s = WEIGHTS["account"] * 0.7
        factors.append(f"New account: only {age} days old")
    else:
        s = 0
    score += s; breakdown["account"] = round(s, 1)

    risk_score = round(min(score, 100), 2)
    risk_level = "LOW"
    for lvl, lo, hi in RISK_LEVELS:
        if lo <= risk_score < hi:
            risk_level = lvl
            break

    return {
        "transaction_id":     row.get("transaction_id", "N/A"),
        "risk_score":         risk_score,
        "risk_level":         risk_level,
        "recommended_action": ACTION_MAP[risk_level],
        "risk_factors":       factors if factors else ["No suspicious signals detected"],
        "score_breakdown":    breakdown,
    }


def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    results   = df.to_dict(orient="records")
    scored    = [compute_risk_score(r) for r in results]
    scored_df = pd.DataFrame(scored)
    return df.merge(
        scored_df[["transaction_id","risk_score","risk_level","recommended_action"]],
        on="transaction_id", how="left"
    )
