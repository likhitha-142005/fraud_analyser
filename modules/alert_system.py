# modules/alert_system.py
# Generates user alerts based on risk score and level

from datetime import datetime

# ── Alert templates per risk level ────────────────────────────────────────────
ALERT_TEMPLATES = {
    "LOW": {
        "icon":    "✅",
        "color":   "#28a745",
        "subject": "Transaction Approved – ₹{amount}",
        "sms":     "Your transaction of ₹{amount} at {merchant} was approved. Ref: {txn_id}",
        "email":   (
            "Dear User,\n\n"
            "Your transaction has been approved successfully.\n\n"
            "  Transaction ID : {txn_id}\n"
            "  Amount         : ₹{amount}\n"
            "  Merchant       : {merchant}\n"
            "  Date & Time    : {timestamp}\n"
            "  Risk Score     : {risk_score}/100 (LOW RISK)\n\n"
            "No suspicious activity was detected.\n\n"
            "Thank you for using our service.\n"
            "Fraud Detection Team"
        ),
        "action": "APPROVE",
    },

    "MEDIUM": {
        "icon":    "⚠️",
        "color":   "#ffc107",
        "subject": "Unusual Transaction Detected – ₹{amount} – Please Verify",
        "sms":     (
            "ALERT: Unusual transaction of ₹{amount} at {merchant} detected. "
            "Risk Score: {risk_score}/100. If this was you, ignore. "
            "If not, call us immediately. Ref: {txn_id}"
        ),
        "email":   (
            "Dear User,\n\n"
            "We noticed an unusual transaction on your account that requires your attention.\n\n"
            "  Transaction ID : {txn_id}\n"
            "  Amount         : ₹{amount}\n"
            "  Merchant       : {merchant}\n"
            "  Location       : {location}\n"
            "  Date & Time    : {timestamp}\n"
            "  Risk Score     : {risk_score}/100 (MEDIUM RISK)\n\n"
            "⚠️  Why this alert was triggered:\n"
            "{risk_factors}\n\n"
            "If this transaction was made by you, no action is needed.\n"
            "If you did NOT make this transaction, please contact us immediately at 1800-XXX-XXXX.\n\n"
            "Fraud Detection Team"
        ),
        "action": "REVIEW",
    },

    "HIGH": {
        "icon":    "🚨",
        "color":   "#fd7e14",
        "subject": "⚠️ HIGH RISK Transaction – Action Required – ₹{amount}",
        "sms":     (
            "HIGH RISK ALERT: Transaction of ₹{amount} at {merchant} has been HELD. "
            "Risk Score: {risk_score}/100. "
            "Reply YES to approve or NO to cancel. Ref: {txn_id}"
        ),
        "email":   (
            "Dear User,\n\n"
            "🚨 A HIGH RISK transaction has been detected and HELD for verification.\n\n"
            "  Transaction ID : {txn_id}\n"
            "  Amount         : ₹{amount}\n"
            "  Merchant       : {merchant}\n"
            "  Location       : {location}\n"
            "  Device         : {device}\n"
            "  Date & Time    : {timestamp}\n"
            "  Risk Score     : {risk_score}/100 (HIGH RISK)\n\n"
            "🔴 Risk Factors Detected:\n"
            "{risk_factors}\n\n"
            "ACTION REQUIRED:\n"
            "  ✅ If this was YOU  → Click here to APPROVE: [Approve Link]\n"
            "  ❌ If this was NOT you → Click here to BLOCK: [Block Link]\n\n"
            "This transaction will remain on HOLD for 24 hours.\n\n"
            "Fraud Detection Team"
        ),
        "action": "HOLD & VERIFY",
    },

    "CRITICAL": {
        "icon":    "🛑",
        "color":   "#dc3545",
        "subject": "🛑 CRITICAL FRAUD ALERT – Transaction BLOCKED – ₹{amount}",
        "sms":     (
            "FRAUD ALERT: Transaction of ₹{amount} at {merchant} has been BLOCKED. "
            "Risk Score: {risk_score}/100. "
            "Your card has been temporarily frozen. Call 1800-XXX-XXXX NOW. Ref: {txn_id}"
        ),
        "email":   (
            "Dear User,\n\n"
            "🛑 CRITICAL: A highly suspicious transaction has been BLOCKED on your account.\n\n"
            "  Transaction ID : {txn_id}\n"
            "  Amount         : ₹{amount}\n"
            "  Merchant       : {merchant}\n"
            "  Location       : {location}\n"
            "  Device         : {device}\n"
            "  Date & Time    : {timestamp}\n"
            "  Risk Score     : {risk_score}/100 (CRITICAL RISK)\n\n"
            "🔴 Fraud Signals Detected:\n"
            "{risk_factors}\n\n"
            "IMMEDIATE ACTIONS TAKEN:\n"
            "  • Transaction has been BLOCKED\n"
            "  • Account flagged for review\n"
            "  • Fraud team has been notified\n\n"
            "WHAT YOU SHOULD DO:\n"
            "  1. Call our 24/7 Fraud Helpline: 1800-XXX-XXXX\n"
            "  2. Change your password immediately\n"
            "  3. Check your recent transactions\n\n"
            "Fraud Detection Team"
        ),
        "action": "BLOCK",
    },
}


def generate_alert(txn: dict, risk_result: dict) -> dict:
    """
    Generate a complete alert object for a transaction.

    Parameters
    ----------
    txn         : raw transaction dict (from CSV row / DB)
    risk_result : output of risk_scorer.compute_risk_score()

    Returns
    -------
    alert dict with sms_message, email_subject, email_body, action, etc.
    """
    level    = risk_result["risk_level"]
    template = ALERT_TEMPLATES[level]

    # Format risk factors as a readable bullet list
    factors_text = "\n".join(
        f"  • {f}" for f in risk_result["risk_factors"]
    )

    fmt = {
        "txn_id":     txn.get("transaction_id", "N/A"),
        "amount":     f"{float(txn.get('amount', 0)):,.2f}",
        "merchant":   txn.get("merchant", "Unknown"),
        "location":   txn.get("location", "Unknown"),
        "device":     txn.get("device", "Unknown"),
        "timestamp":  txn.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "risk_score": risk_result["risk_score"],
        "risk_factors": factors_text,
    }

    return {
        "transaction_id":   fmt["txn_id"],
        "risk_score":       risk_result["risk_score"],
        "risk_level":       level,
        "icon":             template["icon"],
        "color":            template["color"],
        "action":           template["action"],
        "sms_message":      template["sms"].format(**fmt),
        "email_subject":    template["subject"].format(**fmt),
        "email_body":       template["email"].format(**fmt),
        "risk_factors":     risk_result["risk_factors"],
        "alert_time":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "should_notify":    level in ("MEDIUM", "HIGH", "CRITICAL"),
        "should_block":     level == "CRITICAL",
        "should_hold":      level == "HIGH",
    }


def print_alert(alert: dict):
    """Pretty-print an alert to the console (for testing)."""
    print("\n" + "="*60)
    print(f"{alert['icon']}  FRAUD ALERT — {alert['risk_level']}")
    print("="*60)
    print(f"Transaction : {alert['transaction_id']}")
    print(f"Risk Score  : {alert['risk_score']}/100")
    print(f"Action      : {alert['action']}")
    print(f"\n📱 SMS:\n{alert['sms_message']}")
    print(f"\n📧 EMAIL SUBJECT:\n{alert['email_subject']}")
    print(f"\n📧 EMAIL BODY:\n{alert['email_body']}")
    print("="*60)
