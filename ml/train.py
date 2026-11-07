"""Train the XGBoost recovery-risk model on the synthetic dataset.

Run from the project root (after `python ml/generate_data.py`):
    python ml/train.py

Outputs (in ml/models/):
    risk_model.json       the trained XGBoost model
    risk_model_meta.json  feature list, risk thresholds, and evaluation metrics
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score, confusion_matrix, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "synthetic_recovery.csv"
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "risk_model.json"
META_PATH = MODEL_DIR / "risk_model_meta.json"

PROCEDURES = ["orthopedic", "abdominal", "cardiac", "general"]
NUMERIC_FEATURES = [
    "age", "days_since_surgery", "has_diabetes", "is_smoker", "has_obesity",
    "pain_level", "temperature_f", "wound_redness", "wound_drainage", "swelling",
    "nausea", "shortness_of_breath", "mobility_level",
]
FEATURES = NUMERIC_FEATURES + [f"procedure_{p}" for p in PROCEDURES]
LABEL = "complication"

# How the 0-1 score is turned into low / medium / high:
#   high   = escalate to the care team. Lowest threshold where at least 70% of flags are real
#            (keeps false alarms low so clinicians trust the queue).
#   medium = "keep an eye on it". Highest threshold that still catches 90% of complications.
HIGH_MIN_PRECISION = 0.70
MEDIUM_MIN_RECALL = 0.90


def to_features(df: pd.DataFrame) -> pd.DataFrame:
    """Raw columns -> model input columns (one-hot procedure type). Shared with predict.py."""
    X = df[NUMERIC_FEATURES].astype(float).copy()
    for p in PROCEDURES:
        X[f"procedure_{p}"] = (df["procedure_type"] == p).astype(float)
    return X[FEATURES]


def make_model() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=42,
    )


def pick_thresholds(y_true: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    candidates = np.unique(np.round(scores, 3))
    high = next(
        (t for t in candidates if (scores >= t).any()
         and precision_score(y_true, scores >= t, zero_division=0) >= HIGH_MIN_PRECISION),
        0.6,
    )
    medium = max(
        (t for t in candidates if recall_score(y_true, scores >= t) >= MEDIUM_MIN_RECALL),
        default=0.1,
    )
    return float(min(medium, high)), float(high)


def rules_baseline_scores(df: pd.DataFrame) -> np.ndarray:
    """Scores from the old hand-written rules, to show the model is actually better."""
    sys.path.insert(0, str(ROOT.parent / "backend"))
    from app.services.ml_service import score_risk_rules  # noqa: E402

    out = []
    for row in df.to_dict("records"):
        temp = row["temperature_f"]
        symptoms = {**row, "temperature_f": None if pd.isna(temp) else temp}
        patient = {"comorbidities": ["diabetes"] if row["has_diabetes"] else []}
        out.append(score_risk_rules(symptoms, patient)["score"])
    return np.array(out)


def main():
    if not DATA_PATH.exists():
        sys.exit(f"No data at {DATA_PATH}. Run: python ml/generate_data.py")

    df = pd.read_csv(DATA_PATH)
    X, y = to_features(df), df[LABEL].to_numpy()
    X_train, X_test, y_train, y_test, df_train, df_test = train_test_split(
        X, y, df, test_size=0.2, stratify=y, random_state=42
    )

    # 5-fold cross-validation on the training set: is performance stable?
    cv = cross_val_score(make_model(), X_train, y_train, scoring="roc_auc",
                         cv=StratifiedKFold(5, shuffle=True, random_state=42))

    model = make_model().fit(X_train, y_train)
    scores = model.predict_proba(X_test)[:, 1]
    medium_t, high_t = pick_thresholds(y_test, scores)
    flagged = scores >= high_t
    tn, fp, fn, tp = confusion_matrix(y_test, flagged).ravel()

    baseline = rules_baseline_scores(df_test)

    metrics = {
        "rows_train": int(len(y_train)),
        "rows_test": int(len(y_test)),
        "complication_rate": round(float(y.mean()), 4),
        "cv_roc_auc_mean": round(float(cv.mean()), 4),
        "cv_roc_auc_std": round(float(cv.std()), 4),
        "test_roc_auc": round(float(roc_auc_score(y_test, scores)), 4),
        "test_pr_auc": round(float(average_precision_score(y_test, scores)), 4),
        "high_threshold": {
            "precision": round(float(precision_score(y_test, flagged)), 4),
            "recall": round(float(recall_score(y_test, flagged)), 4),
            "true_pos": int(tp), "false_pos": int(fp), "false_neg": int(fn), "true_neg": int(tn),
        },
        "medium_threshold_recall": round(float(recall_score(y_test, scores >= medium_t)), 4),
        "baseline_rules_roc_auc": round(float(roc_auc_score(y_test, baseline)), 4),
        "baseline_rules_pr_auc": round(float(average_precision_score(y_test, baseline)), 4),
    }
    importance = dict(sorted(
        ((f, round(float(v), 4)) for f, v in zip(FEATURES, model.feature_importances_)),
        key=lambda kv: kv[1], reverse=True,
    ))

    MODEL_DIR.mkdir(exist_ok=True)
    model.save_model(MODEL_PATH)
    version = "xgb-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    META_PATH.write_text(json.dumps({
        "model_version": version,
        "trained_on": "synthetic data (ml/generate_data.py), not real patients",
        "features": FEATURES,
        "procedures": PROCEDURES,
        "thresholds": {"medium": round(medium_t, 3), "high": round(high_t, 3)},
        "metrics": metrics,
        "feature_importance": importance,
    }, indent=2))

    m = metrics
    print(f"Model {version} saved to {MODEL_PATH}\n")
    print(f"Cross-validated ROC AUC : {m['cv_roc_auc_mean']:.3f} ± {m['cv_roc_auc_std']:.3f}")
    print(f"Test ROC AUC            : {m['test_roc_auc']:.3f}   (rules baseline {m['baseline_rules_roc_auc']:.3f})")
    print(f"Test PR AUC             : {m['test_pr_auc']:.3f}   (rules baseline {m['baseline_rules_pr_auc']:.3f}, "
          f"random = {m['complication_rate']:.3f})")
    h = m["high_threshold"]
    print(f"\nThresholds: medium >= {medium_t:.3f}, high >= {high_t:.3f}")
    print(f"At 'high': precision {h['precision']:.0%}, recall {h['recall']:.0%} "
          f"(caught {h['true_pos']}, missed {h['false_neg']}, false alarms {h['false_pos']})")
    print(f"At 'medium' or above: catches {m['medium_threshold_recall']:.0%} of complications")
    print("\nTop features:")
    for f, v in list(importance.items())[:8]:
        print(f"  {f:22s} {v:.3f}")


if __name__ == "__main__":
    main()
