import joblib
import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.feature_engineering import get_feature_matrix, add_risk_flags

MODEL_PATH = "models/fraud_model.pkl"

def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run train_model.py first.")
    data = joblib.load(MODEL_PATH)
    return data["model"], data["features"]

def predict_single(txn: dict) -> dict:
    model, features = load_model()
    df = add_risk_flags(pd.DataFrame([txn]))
    X  = get_feature_matrix(df)
    for col in features:
        if col not in X.columns:
            X[col] = 0
    X = X[features]
    prob      = model.predict_proba(X)[0][1]
    predicted = int(model.predict(X)[0])
    return {
        "transaction_id":  txn.get("transaction_id", "N/A"),
        "fraud_probability": round(float(prob), 4),
        "is_fraud_predicted": predicted,
        "confidence": "High" if prob > 0.8 or prob < 0.2 else "Medium"
    }

def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    model, features = load_model()
    df2 = add_risk_flags(df.copy())
    X   = get_feature_matrix(df2)
    for col in features:
        if col not in X.columns:
            X[col] = 0
    X = X[features]
    probs      = model.predict_proba(X)[:, 1]
    predictions = model.predict(X)
    df2["fraud_probability"]  = probs.round(4)
    df2["is_fraud_predicted"] = predictions
    return df2
