# run_risk_alerts.py
# Main pipeline: loads transactions → scores risk → generates alerts → saves results

import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.risk_scorer  import compute_risk_score, score_dataframe
from modules.alert_system import generate_alert, print_alert

# ── 1. Load transactions ───────────────────────────────────────────────────────
print("📂 Loading transactions...")
df = pd.read_csv("data/transactions.csv")
print(f"   {len(df)} transactions loaded\n")

# ── 2. Score every transaction ─────────────────────────────────────────────────
print("⚙️  Calculating risk scores...")
records = df.to_dict(orient="records")

all_scores  = []
all_alerts  = []

for row in records:
    risk   = compute_risk_score(row)
    alert  = generate_alert(row, risk)
    all_scores.append(risk)
    all_alerts.append(alert)

scores_df = pd.DataFrame(all_scores)
alerts_df = pd.DataFrame(all_alerts)

# ── 3. Merge scores back into main df ─────────────────────────────────────────
df = df.merge(
    scores_df[["transaction_id", "risk_score", "risk_level", "recommended_action"]],
    on="transaction_id"
)

# ── 4. Print summary ───────────────────────────────────────────────────────────
print("\n📊 RISK SCORE SUMMARY")
print("─" * 45)
level_counts = df["risk_level"].value_counts()
for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
    count = level_counts.get(level, 0)
    pct   = count / len(df) * 100
    bar   = "█" * int(pct / 2)
    print(f"  {level:<10} {count:>5} ({pct:4.1f}%)  {bar}")

print(f"\n  Avg Risk Score : {df['risk_score'].mean():.2f}/100")
print(f"  Max Risk Score : {df['risk_score'].max():.2f}/100")

# ── 5. Show sample alerts ──────────────────────────────────────────────────────
print("\n\n🔔 SAMPLE ALERTS (one per level):")
for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
    sample = alerts_df[alerts_df["risk_level"] == level]
    if not sample.empty:
        alert_row = sample.iloc[0].to_dict()
        print_alert(alert_row)

# ── 6. Save outputs ────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)

# Full scored transactions CSV
df.to_csv("data/transactions_scored.csv", index=False)

# Alerts only (MEDIUM and above)
alerts_to_send = alerts_df[alerts_df["should_notify"] == True][[
    "transaction_id", "risk_score", "risk_level", "action",
    "sms_message", "email_subject", "email_body", "alert_time"
]]
alerts_to_send.to_csv("data/alerts.csv", index=False)

print(f"\n\n✅ Saved:")
print(f"   data/transactions_scored.csv  ({len(df)} rows with risk scores)")
print(f"   data/alerts.csv               ({len(alerts_to_send)} alerts to send)")
print(f"\n   Breakdown of alerts:")
print(f"   CRITICAL (BLOCK)      : {len(alerts_df[alerts_df['should_block']==True])}")
print(f"   HIGH (HOLD & VERIFY)  : {len(alerts_df[alerts_df['should_hold']==True])}")
print(f"   MEDIUM (REVIEW)       : {len(alerts_df[(alerts_df['risk_level']=='MEDIUM')])}")
print(f"   LOW (no alert needed) : {len(alerts_df[alerts_df['should_notify']==False])}")
