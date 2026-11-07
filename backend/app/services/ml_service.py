"""Recovery risk score for a symptom check-in.

>>> PLACEHOLDER (owned by Person 3 / ML) <<<
This rule-based version exists only so the symptoms endpoint works end to end.
Replace the body of score_risk() with the trained XGBoost model (ml/), but
KEEP THE SAME INPUTS AND OUTPUT so backend/app/routes/symptoms.py keeps working.
"""

MODEL_VERSION = "rules-v0"

# Score thresholds. A "high" score opens an escalation for the care team.
MEDIUM_AT = 0.3
HIGH_AT = 0.6


def score_risk(symptoms: dict, patient: dict) -> dict:
    return score_risk_rules(symptoms, patient)


def score_risk_rules(symptoms: dict, patient: dict) -> dict:
    """Hand-written rules. Also used as the baseline that ml/train.py compares against.

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
