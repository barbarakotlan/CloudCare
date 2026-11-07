"""Generate a SYNTHETIC post-op recovery dataset for training the risk model.

No real patient data is used. Each row is one symptom check-in for a fake patient,
labeled with whether that patient went on to have a complication within 7 days.

Patterns built in (loosely based on common post-op warning signs):
  - Older age, diabetes, smoking, obesity and cardiac/abdominal surgery raise baseline risk.
  - Patients heading toward a complication more often report fever, wound redness/drainage,
    rising pain, shortness of breath and lower mobility.
  - Plenty of noise and overlap, so the model can't be perfect (like real life).

Column names match the symptom_logs table so the trained model can score real check-ins.

Run from the project root:
    python ml/generate_data.py            # 5000 rows -> ml/data/synthetic_recovery.csv
    python ml/generate_data.py --rows 20000
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OUT_PATH = Path(__file__).parent / "data" / "synthetic_recovery.csv"

PROCEDURES = ["orthopedic", "abdominal", "cardiac", "general"]
PROCEDURE_WEIGHTS = [0.35, 0.30, 0.15, 0.20]
PROCEDURE_RISK = {"orthopedic": 0.0, "abdominal": 0.35, "cardiac": 0.6, "general": -0.2}


def generate(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # ---- Who the patient is -------------------------------------------------
    age = rng.normal(58, 14, n).clip(18, 95).round().astype(int)
    procedure = rng.choice(PROCEDURES, size=n, p=PROCEDURE_WEIGHTS)
    days_since_surgery = rng.integers(1, 31, n)
    has_diabetes = rng.random(n) < (0.10 + 0.004 * (age - 40)).clip(0.05, 0.35)
    is_smoker = rng.random(n) < 0.15
    has_obesity = rng.random(n) < 0.30

    # ---- Hidden baseline risk -> did a complication happen? ------------------
    logit = (
        -3.0
        + 0.03 * (age - 58)
        + 0.6 * has_diabetes
        + 0.5 * is_smoker
        + 0.35 * has_obesity
        + np.vectorize(PROCEDURE_RISK.get)(procedure)
        - 0.04 * (days_since_surgery - 7)   # early days are riskier
        + rng.normal(0, 0.6, n)             # things we can't measure
    )
    complication = rng.random(n) < 1 / (1 + np.exp(-logit))
    c = complication.astype(float)

    # ---- What they report at check-in (shifted if heading to a complication) --
    healing_pain = (6 - 0.15 * days_since_surgery).clip(1, 6)
    pain_level = (healing_pain + 2.2 * c + rng.normal(0, 1.6, n)).round().clip(0, 10).astype(int)

    fever_bump = np.where(complication & (rng.random(n) < 0.55), rng.normal(2.4, 0.9, n), 0)
    temperature_f = (rng.normal(98.6, 0.6, n) + fever_bump).clip(96, 105).round(1)
    # About 30% of people don't take their temperature.
    temperature_f = np.where(rng.random(n) < 0.30, np.nan, temperature_f)

    def symptom(base: float, extra_if_complication: float) -> np.ndarray:
        return rng.random(n) < (base + extra_if_complication * c)

    wound_redness = symptom(0.10, 0.40)
    wound_drainage = symptom(0.05, 0.35)
    swelling = symptom(0.30, 0.25)
    nausea = symptom(0.10, 0.20)
    sob_extra = np.where(procedure == "cardiac", 0.35, 0.12)
    shortness_of_breath = rng.random(n) < (0.03 + sob_extra * c)

    expected_mobility = (1.5 + 0.12 * days_since_surgery - 0.015 * (age - 58)).clip(0, 4)
    mobility_level = (expected_mobility - 1.1 * c + rng.normal(0, 0.8, n)).round().clip(0, 4).astype(int)

    return pd.DataFrame({
        # patient
        "age": age,
        "procedure_type": procedure,
        "days_since_surgery": days_since_surgery,
        "has_diabetes": has_diabetes.astype(int),
        "is_smoker": is_smoker.astype(int),
        "has_obesity": has_obesity.astype(int),
        # check-in (same names as symptom_logs)
        "pain_level": pain_level,
        "temperature_f": temperature_f,
        "wound_redness": wound_redness.astype(int),
        "wound_drainage": wound_drainage.astype(int),
        "swelling": swelling.astype(int),
        "nausea": nausea.astype(int),
        "shortness_of_breath": shortness_of_breath.astype(int),
        "mobility_level": mobility_level,
        # label
        "complication": complication.astype(int),
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = generate(args.rows, args.seed)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"Wrote {len(df):,} rows to {OUT_PATH}")
    print(f"Complication rate: {df['complication'].mean():.1%}")
    print("\nAverage by outcome (0 = recovered fine, 1 = complication):")
    cols = ["age", "pain_level", "temperature_f", "wound_redness", "wound_drainage",
            "shortness_of_breath", "mobility_level"]
    print(df.groupby("complication")[cols].mean().round(2).T.to_string())


if __name__ == "__main__":
    main()
