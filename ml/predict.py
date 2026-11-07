"""Score one check-in with the trained risk model, and explain the score.

Used by the backend (backend/app/services/ml_service.py). Can also be run directly:
    python ml/predict.py          # scores two example check-ins
"""

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import xgboost as xgb

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "risk_model.json"
META_PATH = MODEL_DIR / "risk_model_meta.json"


class RiskModel:
    def __init__(self, model_path: Path = MODEL_PATH, meta_path: Path = META_PATH):
        self.meta = json.loads(meta_path.read_text())
        self.features: list[str] = self.meta["features"]
        self.procedures: list[str] = self.meta["procedures"]
        self.thresholds: dict = self.meta["thresholds"]
        self.version: str = self.meta["model_version"]
        self.booster = xgb.Booster()
        self.booster.load_model(model_path)

    def _vector(self, symptoms: dict, patient: dict) -> np.ndarray:
        """Backend dicts -> one row in the exact column order the model was trained on."""
        comorbidities = {c.lower() for c in (patient.get("comorbidities") or [])}

        def num(v):
            return math.nan if v is None else float(v)  # XGBoost treats NaN as "unknown"

        values = {
            "age": num(patient.get("age")),
            "days_since_surgery": num(patient.get("days_since_surgery")),
            "has_diabetes": float("diabetes" in comorbidities),
            "is_smoker": float("smoker" in comorbidities or "smoking" in comorbidities),
            "has_obesity": float("obesity" in comorbidities),
            "pain_level": num(symptoms.get("pain_level")),
            "temperature_f": num(symptoms.get("temperature_f")),
            "wound_redness": float(bool(symptoms.get("wound_redness"))),
            "wound_drainage": float(bool(symptoms.get("wound_drainage"))),
            "swelling": float(bool(symptoms.get("swelling"))),
            "nausea": float(bool(symptoms.get("nausea"))),
            "shortness_of_breath": float(bool(symptoms.get("shortness_of_breath"))),
            "mobility_level": num(symptoms.get("mobility_level")),
        }
        for p in self.procedures:
            values[f"procedure_{p}"] = float(patient.get("procedure_type") == p)
        return np.array([[values[f] for f in self.features]])

    def predict(self, symptoms: dict, patient: dict) -> dict:
        """Same output shape as score_risk() in the backend."""
        dm = xgb.DMatrix(self._vector(symptoms, patient), feature_names=self.features, missing=math.nan)
        score = float(self.booster.predict(dm)[0])

        # Per-feature contributions (SHAP values, in log-odds). Last column is the baseline.
        contribs = self.booster.predict(dm, pred_contribs=True)[0][:-1]
        merged: dict[str, float] = {}
        for name, value in zip(self.features, contribs):
            key = "procedure_type" if name.startswith("procedure_") else name
            merged[key] = merged.get(key, 0.0) + float(value)
        top = sorted(
            ({"feature": f, "impact": round(v, 3)} for f, v in merged.items() if v > 0.05),
            key=lambda x: x["impact"], reverse=True,
        )[:3]

        if score >= self.thresholds["high"]:
            level = "high"
        elif score >= self.thresholds["medium"]:
            level = "medium"
        else:
            level = "low"

        return {"score": round(score, 3), "risk_level": level, "top_factors": top, "model_version": self.version}


@lru_cache(maxsize=1)
def load_model() -> RiskModel:
    """Loaded once, then reused for every request."""
    return RiskModel()


if __name__ == "__main__":
    model = load_model()
    patient = {"procedure_type": "orthopedic", "days_since_surgery": 3, "age": 64, "comorbidities": ["diabetes"]}
    examples = {
        "doing well": {"pain_level": 3, "temperature_f": 98.4, "mobility_level": 3},
        "warning signs": {"pain_level": 8, "temperature_f": 101.9, "wound_redness": True,
                          "wound_drainage": True, "mobility_level": 1},
    }
    print(f"Model {model.version}, thresholds {model.thresholds}\n")
    for name, symptoms in examples.items():
        print(f"{name:14s} -> {model.predict(symptoms, patient)}")
