# modules/feature_engineering.py
# Transforms raw transaction data into ML-ready features

import pandas as pd
import numpy as np

FEATURE_COLUMNS = [
    "amount", "hour_of_day", "day_of_week", "failed_attempts",
    "txn_velocity", "account_age_days", "amount_deviation",
    "is_foreign_location", "is_unusual_device"
]

def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode merchant, location, device, payment_method."""
    df = pd.get_dummies(df, columns=["payment_method"], drop_first=True)
    return df

def add_risk_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived binary risk flags."""
    df = df.copy()
    df["is_high_amount"]    = (df["amount"] > 50000).astype(int)
    df["is_odd_hour"]       = df["hour_of_day"].apply(
                                lambda h: 1 if h < 5 or h > 22 else 0)
    df["is_new_account"]    = (df["account_age_days"] < 30).astype(int)
    df["is_high_velocity"]  = (df["txn_velocity"] > 5).astype(int)
    df["is_high_deviation"] = (df["amount_deviation"] > 5).astype(int)
    return df

def get_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Full pipeline: flags → encode → return X matrix."""
    df = add_risk_flags(df)
    extended_features = FEATURE_COLUMNS + [
        "is_high_amount", "is_odd_hour", "is_new_account",
        "is_high_velocity", "is_high_deviation"
    ]
    # Keep only columns that exist
    cols = [c for c in extended_features if c in df.columns]
    return df[cols].fillna(0)

def prepare_single_transaction(txn: dict, user_avg_amount: float) -> pd.DataFrame:
    """Prepare a single transaction dict for real-time prediction."""
    txn["amount_deviation"]     = round(txn["amount"] / max(user_avg_amount, 1), 4)
    txn["is_foreign_location"]  = 1 if txn.get("location") in [
        "Dubai", "Singapore", "London", "USA", "Unknown_Location"] else 0
    txn["is_unusual_device"]    = 0  # set by caller if known
    return get_feature_matrix(pd.DataFrame([txn]))
