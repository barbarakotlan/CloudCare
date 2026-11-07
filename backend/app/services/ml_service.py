"""Recovery risk score for a symptom check-in.

score_risk() uses the trained XGBoost model from ml/ (see ml/train.py and ml/predict.py).
If the model can't be loaded (file missing, xgboost not installed), it falls back to the
hand-written rules below so the app never breaks.
"""

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# Make the project's ml/ folder importable from the backend.
ML_DIR = Path(__file__).resolve().parents[3] / "ml"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

MODEL_VERSION = "rules-v0"

# Score thresholds for the fallback rules. A "high" score opens an escalation.
MEDIUM_AT = 0.3
HIGH_AT = 0.6


def score_risk(symptoms: dict, patient: dict) -> dict:
    """
    Inputs:
      symptoms: one check-in, same keys as the symptom_logs table:
                pain_level, temperature_f, wound_redness, wound_drainage, swelling,
                nausea, shortness_of_breath, mobility_level
      patient:  {"procedure_type", "days_since_surgery", "age", "comorbidities"}

    Returns a dict:
      {
        "score": float,                 # 0..1
        "risk_level": "low" | "medium" | "high",
        "top_factors": [{"feature": str, "impact": float}],   # biggest first, max 3
        "model_version": str,
      }
    """
    try:
        from predict import load_model  # ml/predict.py

        return load_model().predict(symptoms, patient)
    except Exception:
        log.exception("Risk model unavailable, using fallback rules")
        return score_risk_rules(symptoms, patient)


def score_risk_rules(symptoms: dict, patient: dict) -> dict:
    """Hand-written rules. Fallback if the model can't load, and the baseline ml/train.py compares against."""
    temp = symptoms.get("temperature_f")
    pain = symptoms.get("pain_level") or 0
    mobility = symptoms.get("mobility_level")

    factors = {
        "temperature_f": 0.30 if temp is not None and temp >= 100.4 else 0.0,
        "shortness_of_breath": 0.35 if symptoms.get("shortness_of_breath") else 0.0,
        "wound_drainage": 0.15 if symptoms.get("wound_drainage") else 0.0,
        "wound_redness": 0.15 if symptoms.get("wound_redness") else 0.0,
        "pain_level": 0.15 if pain >= 7 else pain * 0.01,
        "mobility_level": 0.10 if mobility is not None and mobility <= 1 else 0.0,
        "swelling": 0.05 if symptoms.get("swelling") else 0.0,
        "nausea": 0.05 if symptoms.get("nausea") else 0.0,
    }
    if "diabetes" in (patient.get("comorbidities") or []):
        factors["comorbidities"] = 0.05

    score = min(0.97, 0.05 + sum(factors.values()))
    top = sorted(
        ({"feature": f, "impact": round(v, 3)} for f, v in factors.items() if v > 0),
        key=lambda x: x["impact"],
        reverse=True,
    )[:3]

    return {
        "score": round(score, 3),
        "risk_level": "high" if score >= HIGH_AT else "medium" if score >= MEDIUM_AT else "low",
        "top_factors": top,
        "model_version": MODEL_VERSION,
    }
