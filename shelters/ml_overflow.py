"""
shelters/ml_overflow.py
────────────────────────────────────────────────────────────────
Shelter Overflow Risk Prediction using Gradient Boosting Classifier.

Why Gradient Boosting?
  - Handles small/imbalanced datasets better than Random Forest
  - Gives calibrated probability scores (great for Low / Medium / High)
  - Robust to noisy real-world data
  - Explainable feature importances

When no trained model exists yet, falls back to a deterministic
rule-based scoring system so the dashboard always works.
────────────────────────────────────────────────────────────────
"""

import os
import pickle
import logging
import numpy as np
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "overflow_model.pkl")

# ─────────────────────────────────────────────
# FEATURE EXTRACTION
# ─────────────────────────────────────────────

def extract_features(shelter, weather_data: dict = None) -> dict:
    """
    Build a feature dict for a shelter.
    Pulls last 6 status updates for trend analysis.
    """
    from .models import ShelterStatusUpdate

    updates = list(
        ShelterStatusUpdate.objects
        .filter(shelter=shelter)
        .order_by("-updated_at")[:6]
    )

    occupancy_pct = shelter.occupancy_pct
    current_occ   = shelter.current_occupancy
    max_cap       = shelter.max_capacity or 1

    # ── Occupancy trend (slope over last N updates) ──
    if len(updates) >= 2:
        occ_values = [u.current_occupancy for u in updates][::-1]  # oldest first
        x = np.arange(len(occ_values))
        slope = float(np.polyfit(x, occ_values, 1)[0])             # people/update
    else:
        slope = 0.0

    # ── Hours since last update ──
    hours_since_update = 0
    if updates:
        delta = timezone.now() - updates[0].updated_at
        hours_since_update = delta.total_seconds() / 3600

    # ── Supply stress ──
    latest = updates[0] if updates else None
    food_stress  = {"ok": 0, "low": 1, "critical": 2, "out": 3}.get(
        getattr(latest, "food_status",  "ok"), 0)
    water_stress = {"ok": 0, "low": 1, "critical": 2, "out": 3}.get(
        getattr(latest, "water_status", "ok"), 0)

    # ── Volunteer ratio (active volunteers / 10 people) ──
    active_vols = shelter.volunteers.filter(status="active").count()
    vol_ratio   = active_vols / max(current_occ, 1) * 10  # vols per 10 occupants

    # ── Weather severity ──
    rain_prob = 0
    if weather_data:
        rain_prob = weather_data.get("rain_probability", 0) or weather_data.get("rain_1h", 0)

    return {
        "occupancy_pct":       occupancy_pct,
        "occupancy_trend":     slope,          # positive = filling fast
        "hours_since_update":  hours_since_update,
        "food_stress":         food_stress,
        "water_stress":        water_stress,
        "volunteer_ratio":     vol_ratio,
        "rain_probability":    rain_prob,
        "has_medical":         int(shelter.has_medical),
        "nearby_available":    _count_nearby_capacity(shelter),
    }


def _count_nearby_capacity(shelter) -> int:
    """
    Count total remaining capacity in shelters of the same district
    excluding the current shelter (proxy for 'relief pressure nearby').
    """
    from .models import Shelter, ShelterStatusUpdate
    others = Shelter.objects.filter(
        district=shelter.district,
        status="active"
    ).exclude(id=shelter.id)

    total_free = 0
    for s in others:
        latest = s.status_updates.order_by("-updated_at").first()
        occ = latest.current_occupancy if latest else 0
        total_free += max(0, s.max_capacity - occ)
    return total_free


# ─────────────────────────────────────────────
# RULE-BASED FALLBACK (always available)
# ─────────────────────────────────────────────

def _rule_based_risk(features: dict) -> dict:
    """
    Deterministic scoring when ML model is not trained yet.
    Returns same structure as ML predict.
    """
    score = 0

    occ_pct = features["occupancy_pct"]
    if occ_pct >= 90:
        score += 40
    elif occ_pct >= 75:
        score += 25
    elif occ_pct >= 60:
        score += 10

    trend = features["occupancy_trend"]
    if trend > 5:
        score += 20
    elif trend > 2:
        score += 10
    elif trend > 0:
        score += 5

    score += features["food_stress"]  * 8
    score += features["water_stress"] * 8

    if features["rain_probability"] > 70:
        score += 10
    elif features["rain_probability"] > 40:
        score += 5

    nearby = features["nearby_available"]
    if nearby < 20:
        score += 10
    elif nearby < 50:
        score += 5

    probability = min(score / 100, 0.99)

    if probability >= 0.65:
        risk = "high"
    elif probability >= 0.35:
        risk = "medium"
    else:
        risk = "low"

    return {
        "risk":        risk,
        "probability": round(probability, 3),
        "method":      "rule_based",
        "features":    features,
    }


# ─────────────────────────────────────────────
# TRAIN (call this periodically / on demand)
# ─────────────────────────────────────────────

def train_overflow_model():
    """
    Train Gradient Boosting model from historical ShelterStatusUpdate data.
    Labels are auto-generated: occupancy >= 85% of capacity → positive class.
    Saves model to overflow_model.pkl.
    """
    from .models import Shelter, ShelterStatusUpdate
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    from sklearn.preprocessing import label_binarize

    rows = []
    labels = []

    shelters = Shelter.objects.all()
    for shelter in shelters:
        updates = list(
            ShelterStatusUpdate.objects
            .filter(shelter=shelter)
            .order_by("updated_at")
        )

        for i in range(2, len(updates)):
            # Use updates[0..i-1] as history, updates[i] as label
            snapshot_updates = updates[:i]
            future_update    = updates[i]

            # Temporarily set current occupancy context
            occ_pct   = (future_update.current_occupancy / (shelter.max_capacity or 1)) * 100
            food_s    = {"ok": 0, "low": 1, "critical": 2, "out": 3}.get(future_update.food_status, 0)
            water_s   = {"ok": 0, "low": 1, "critical": 2, "out": 3}.get(future_update.water_status, 0)

            occ_values = [u.current_occupancy for u in snapshot_updates[-6:]]
            slope = float(np.polyfit(range(len(occ_values)), occ_values, 1)[0]) if len(occ_values) >= 2 else 0.0

            feat = [
                (snapshot_updates[-1].current_occupancy / (shelter.max_capacity or 1)) * 100,
                slope,
                0,          # hours_since_update — not meaningful for training
                food_s,
                water_s,
                1.0,        # volunteer_ratio default
                0,          # rain_probability — not available historically
                int(shelter.has_medical),
                0,          # nearby_available
            ]
            rows.append(feat)

            # Label: 0=low, 1=medium, 2=high
            if occ_pct >= 85:
                labels.append(2)
            elif occ_pct >= 65:
                labels.append(1)
            else:
                labels.append(0)

    if len(rows) < 20:
        logger.warning("Not enough training data (%d rows). Need at least 20.", len(rows))
        return False

    X = np.array(rows)
    y = np.array(labels)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = GradientBoostingClassifier(
        n_estimators=150,
        learning_rate=0.08,
        max_depth=4,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    report = classification_report(y_test, y_pred, target_names=["low", "medium", "high"], zero_division=0)
    logger.info("Overflow model trained:\n%s", report)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    logger.info("Model saved to %s", MODEL_PATH)
    return report


# ─────────────────────────────────────────────
# PREDICT (main entry point)
# ─────────────────────────────────────────────

def predict_overflow_risk(shelter, weather_data: dict = None) -> dict:
    """
    Main prediction function.
    Returns: { risk, probability, method, features }
    """
    features = extract_features(shelter, weather_data)

    # Try ML model first
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)

            feat_array = np.array([[
                features["occupancy_pct"],
                features["occupancy_trend"],
                features["hours_since_update"],
                features["food_stress"],
                features["water_stress"],
                features["volunteer_ratio"],
                features["rain_probability"],
                features["has_medical"],
                features["nearby_available"],
            ]])

            pred_label = model.predict(feat_array)[0]
            proba      = model.predict_proba(feat_array)[0]

            risk_map = {0: "low", 1: "medium", 2: "high"}
            return {
                "risk":        risk_map[pred_label],
                "probability": round(float(proba.max()), 3),
                "method":      "gradient_boosting",
                "features":    features,
            }
        except Exception as e:
            logger.error("ML prediction failed, falling back to rules: %s", e)

    # Fallback
    return _rule_based_risk(features)
