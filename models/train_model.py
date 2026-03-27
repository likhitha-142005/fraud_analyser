# models/train_model.py
# Trains Random Forest fraud detection model and saves it

import pandas as pd
import numpy as np
import joblib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.ensemble         import RandomForestClassifier
from sklearn.model_selection  import train_test_split, cross_val_score
from sklearn.metrics          import (classification_report,
                                      confusion_matrix, roc_auc_score)
from sklearn.preprocessing    import StandardScaler

from modules.feature_engineering import get_feature_matrix, add_risk_flags

# ─── Load data ─────────────────────────────────────────────────────────────────
print("📂 Loading data...")
df = pd.read_csv("data/transactions.csv")
print(f"   {len(df)} transactions | Fraud: {df['is_fraud'].sum()} ({df['is_fraud'].mean()*100:.1f}%)")

# ─── Feature engineering ───────────────────────────────────────────────────────
print("\n⚙️  Engineering features...")
df = add_risk_flags(df)
X = get_feature_matrix(df)
y = df["is_fraud"]
print(f"   Features used: {list(X.columns)}")

# ─── Train/test split ──────────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\n📊 Train: {len(X_train)} | Test: {len(X_test)}")

# ─── Train model ───────────────────────────────────────────────────────────────
print("\n🤖 Training Random Forest model...")
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    class_weight="balanced",   # handles class imbalance
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# ─── Evaluate ──────────────────────────────────────────────────────────────────
y_pred  = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

print("\n📈 RESULTS:")
print("─" * 50)
print(classification_report(y_test, y_pred, target_names=["Legit", "Fraud"]))
print(f"ROC-AUC Score : {roc_auc_score(y_test, y_proba):.4f}")
print(f"\nConfusion Matrix:\n{confusion_matrix(y_test, y_pred)}")

# Feature importance
importance = pd.Series(model.feature_importances_, index=X.columns)
print(f"\n🔑 Top Features:\n{importance.sort_values(ascending=False).head(8)}")

# ─── Save model ────────────────────────────────────────────────────────────────
os.makedirs("models", exist_ok=True)
joblib.dump({"model": model, "features": list(X.columns)}, "models/fraud_model.pkl")
print("\n✅ Model saved to models/fraud_model.pkl")
