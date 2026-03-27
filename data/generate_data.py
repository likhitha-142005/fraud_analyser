"""
Fraud Transaction Sample Data Generator
Generates realistic synthetic transaction data for training/testing
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

np.random.seed(42)
random.seed(42)

# ─── Config ────────────────────────────────────────────────────────────────────
N_USERS       = 500
N_TRANSACTIONS = 10000
FRAUD_RATE     = 0.08   # 8% fraud (realistic imbalance)

# ─── Reference data ────────────────────────────────────────────────────────────
MERCHANTS = [
    "Amazon", "Flipkart", "Swiggy", "Zomato", "BigBasket",
    "Myntra", "PhonePe Store", "PayTM Mall", "BookMyShow",
    "MakeMyTrip", "Uber", "Ola", "Nykaa", "Meesho", "Unknown_Merchant"
]

DEVICES = ["Android", "iOS", "Windows", "MacOS", "Linux"]

LOCATIONS = [
    "Hyderabad", "Mumbai", "Delhi", "Bangalore", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat",
    "Dubai", "Singapore", "Unknown_Location", "London", "USA"
]

PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Net Banking", "Wallet"]

# ─── Generate users ────────────────────────────────────────────────────────────
users = []
for uid in range(1, N_USERS + 1):
    users.append({
        "user_id": f"U{uid:04d}",
        "home_location": random.choice(LOCATIONS[:10]),   # domestic only
        "usual_device": random.choice(DEVICES[:3]),
        "avg_txn_amount": round(np.random.lognormal(mean=7, sigma=1), 2),  # ₹~1000 avg
        "account_age_days": random.randint(30, 2000)
    })
user_df = pd.DataFrame(users)

# ─── Generate transactions ─────────────────────────────────────────────────────
records = []
start_date = datetime(2024, 1, 1)

for i in range(N_TRANSACTIONS):
    user = user_df.sample(1).iloc[0]
    is_fraud = random.random() < FRAUD_RATE

    txn_date = start_date + timedelta(
        days=random.randint(0, 365),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )

    if is_fraud:
        # Fraud patterns: unusual amount, odd hour, foreign location, unknown merchant
        amount = round(np.random.choice([
            np.random.uniform(50000, 200000),   # very high amount
            np.random.uniform(1, 10),            # micro transactions (card testing)
            user["avg_txn_amount"] * np.random.uniform(10, 50)
        ]), 2)
        location = random.choice(LOCATIONS[10:])  # foreign/unknown location
        device = random.choice(DEVICES)
        merchant = random.choice(["Unknown_Merchant"] + MERCHANTS[-3:])
        hour = random.choice(list(range(0, 5)) + list(range(22, 24)))  # odd hours
        payment_method = random.choice(PAYMENT_METHODS)
        failed_attempts = random.randint(1, 5)
        velocity = random.randint(5, 20)   # many txns in short time
    else:
        # Normal patterns
        amount = round(max(10, np.random.lognormal(
            mean=np.log(max(user["avg_txn_amount"], 1)), sigma=0.5)), 2)
        location = random.choices(
            [user["home_location"]] + LOCATIONS[:10],
            weights=[7] + [0.3]*10
        )[0]
        device = random.choices(
            [user["usual_device"]] + DEVICES,
            weights=[8] + [0.5]*5
        )[0]
        merchant = random.choice(MERCHANTS[:-1])
        hour = txn_date.hour
        payment_method = random.choice(PAYMENT_METHODS)
        failed_attempts = random.choices([0, 1, 2], weights=[85, 10, 5])[0]
        velocity = random.randint(1, 4)

    records.append({
        "transaction_id":   f"TXN{i+1:06d}",
        "user_id":          user["user_id"],
        "timestamp":        txn_date.strftime("%Y-%m-%d %H:%M:%S"),
        "amount":           amount,
        "merchant":         merchant,
        "location":         location,
        "device":           device,
        "payment_method":   payment_method,
        "hour_of_day":      hour,
        "day_of_week":      txn_date.weekday(),       # 0=Mon, 6=Sun
        "failed_attempts":  failed_attempts,
        "txn_velocity":     velocity,                  # txns by user in last 1hr
        "account_age_days": user["account_age_days"],
        "avg_user_amount":  user["avg_txn_amount"],
        "amount_deviation": round(amount / max(user["avg_txn_amount"], 1), 4),
        "is_foreign_location": int(location in LOCATIONS[10:]),
        "is_unusual_device":   int(device != user["usual_device"]),
        "is_fraud":         int(is_fraud)
    })

df = pd.DataFrame(records)

# ─── Save ──────────────────────────────────────────────────────────────────────
df.to_csv("/home/claude/fraud_analyser/data/transactions.csv", index=False)

print(f"✅ Dataset generated: {len(df)} transactions")
print(f"   Fraud cases  : {df['is_fraud'].sum()} ({df['is_fraud'].mean()*100:.1f}%)")
print(f"   Legit cases  : {(df['is_fraud']==0).sum()}")
print(f"\nColumns: {list(df.columns)}")
print(f"\nSample fraud transaction:\n{df[df['is_fraud']==1].iloc[0].to_dict()}")
