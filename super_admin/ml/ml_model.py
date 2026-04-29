# =============================================================================
# super_admin/ml/ml_model.py
# =============================================================================
# Kerala Flood Risk Prediction Engine — with XAI (Explainable AI via SHAP)
#
# What this file does:
#   1. Loads the trained Random Forest model and its config from .pkl files
#   2. Takes live weather data for a district as input
#   3. Engineers 15 features from raw weather values
#   4. Runs the Random Forest prediction → risk level + confidence %
#   5. Runs SHAP TreeExplainer → explains WHY the model made that prediction
#   6. Returns everything as a dict for the Django view and template
#
# XAI (Explainable AI):
#   SHAP (SHapley Additive exPlanations) assigns each input feature a
#   numerical "contribution score" to the final prediction. Positive SHAP
#   values push the prediction toward the predicted class (e.g., HIGH risk).
#   Negative values push away from it. This makes the black-box Random Forest
#   fully interpretable for administrators and decision-makers.
# =============================================================================

import pickle
import numpy as np
import os
import shap          # XAI library — SHAP (SHapley Additive exPlanations)
import pandas as pd
from django.conf import settings
from datetime import datetime


# =============================================================================
# 📌 PATH SETUP — locate model files relative to Django BASE_DIR
# =============================================================================

BASE_DIR  = settings.BASE_DIR
MODEL_DIR = os.path.join(BASE_DIR, "super_admin", "ml")


# =============================================================================
# 📌 LOAD TRAINED MODEL AND CONFIG
# Loaded once at module import time (not on every request — saves memory)
# =============================================================================

with open(os.path.join(MODEL_DIR, "kerala_flood_model.pkl"), "rb") as f:
    model = pickle.load(f)

with open(os.path.join(MODEL_DIR, "model_config.pkl"), "rb") as f:
    config = pickle.load(f)

print(f"[ML MODEL] Loaded: {type(model).__name__}")

# =============================================================================
# 📌 UNPACK CONFIG
# label_encoder    → encodes/decodes district names to integers
# target_encoder   → encodes/decodes risk labels (Low/Medium/High)
# district_mapping → {district_name: integer_code}
# feature_columns  → ordered list of 15 feature names the model expects
# =============================================================================

label_encoder    = config["label_encoder"]
target_encoder   = config["target_encoder"]
district_mapping = config["district_mapping"]
feature_columns  = config["feature_columns"]


# =============================================================================
# 📌 PRE-BUILD SHAP EXPLAINER
# TreeExplainer is the fastest SHAP method for tree-based models like
# Random Forest. Built once here so every prediction reuses it — avoids
# rebuilding the explainer on every request (expensive operation).
#
# NOTE: We also use shap.Explainer() inside predict_flood_risk() because
# it returns a consistent Explanation object across SHAP versions (0.41+).
# _shap_explainer is kept as fallback reference.
# =============================================================================

_shap_explainer = shap.TreeExplainer(model)
print("[ML MODEL] SHAP TreeExplainer ready")


# =============================================================================
# 🌊 DEMO OVERRIDE SYSTEM
# Used only for demo/testing to simulate extreme flood conditions in
# specific districts. Does NOT affect production live-weather predictions
# when demo_mode=False.
# =============================================================================

DEMO_DISTRICT_OVERRIDES = {
    "Pathanamthitta": {
        "rain_1h": 120,   # Force heavy rainfall for demo
        "humidity": 92    # Force high humidity for demo
    },
    "Wayanad": {
        "rain_1h": 90,
        "humidity": 88
    },
    "Idukki": {
        "rain_1h": 75,
        "humidity": 85
    }
}


# =============================================================================
# 📌 HUMAN-READABLE FEATURE LABELS
# Maps internal feature column names to user-friendly display names
# shown in the XAI explanation panel on the prediction page.
# =============================================================================

FEATURE_LABELS = {
    "District_Encoded":    "District",
    "Month":               "Month",
    "Daily_Rainfall_mm":   "Rainfall (1h)",
    "Rainfall_7day_mm":    "Rainfall (7-day est.)",
    "Rainfall_30day_mm":   "Rainfall (30-day est.)",
    "Wind_Speed_kmh":      "Wind Speed",
    "Temperature_C":       "Temperature",
    "Humidity_pct":        "Humidity",
    "Pressure_hPa":        "Pressure",
    "Elevation_m":         "Elevation",
    "River_Proximity":     "River Proximity",
    "Drainage_Capacity":   "Drainage Capacity",
    "Population_Density":  "Population Density",
    "Soil_Moisture_pct":   "Soil Moisture",
    "Is_Monsoon":          "Is Monsoon Season",
    "Is_Heavy_Rain":       "Is Heavy Rain",
    "Low_Elevation":       "Low Elevation Zone",
    "Poor_Drainage":       "Poor Drainage",
    "High_Soil_Moisture":  "High Soil Moisture",
}

# Units for display alongside values in the explanation panel
FEATURE_UNITS = {
    "Daily_Rainfall_mm":  "mm",
    "Rainfall_7day_mm":   "mm",
    "Rainfall_30day_mm":  "mm",
    "Wind_Speed_kmh":     "km/h",
    "Temperature_C":      "°C",
    "Humidity_pct":       "%",
    "Pressure_hPa":       "hPa",
    "Elevation_m":        "m",
    "Soil_Moisture_pct":  "%",
}


# =============================================================================
# 📌 PLAIN ENGLISH INTERPRETATION
# Generates a human-readable sentence for each feature's SHAP contribution.
# This makes the XAI panel understandable to non-technical users like
# district officials and emergency responders.
# =============================================================================

def get_plain_english(col, value, shap_value, risk_label):
    """
    Returns a plain English sentence explaining what this feature's
    value means and how it influenced the flood risk prediction.
    """
    direction = "increases" if shap_value > 0 else "reduces"
    impact    = abs(shap_value)
    strong    = impact > 0.10   # large contribution
    moderate  = impact > 0.04   # moderate contribution

    # ── Rainfall (1h) ──────────────────────────────────────────────────
    if col == "Daily_Rainfall_mm":
        if value == 0:
            return "No rainfall recorded in the last hour — safe conditions."
        elif value < 10:
            return f"Light rain ({value}mm/hr) — low flood concern."
        elif value < 50:
            return f"Moderate rain ({value}mm/hr) — monitoring advised."
        elif value < 100:
            return f"Heavy rain ({value}mm/hr) — significant flood risk signal."
        else:
            return f"Extreme rainfall ({value}mm/hr) — major flood danger. This strongly pushed the prediction to {risk_label}."

    # ── Rainfall 7-day ─────────────────────────────────────────────────
    elif col == "Rainfall_7day_mm":
        if value == 0:
            return "No sustained rainfall over the past week — ground is dry."
        elif value < 500:
            return f"Low weekly rainfall estimate ({value}mm) — soil not saturated."
        elif value < 1500:
            return f"Moderate weekly rainfall ({value}mm) — soil moisture building up."
        else:
            return f"Very high weekly rainfall estimate ({value}mm) — soil is likely saturated, runoff risk is high."

    # ── Rainfall 30-day ────────────────────────────────────────────────
    elif col == "Rainfall_30day_mm":
        if value == 0:
            return "Dry month — no cumulative rainfall pressure on drainage."
        elif value < 3000:
            return f"Monthly rainfall ({value}mm) within normal range."
        else:
            return f"Exceptionally high monthly rainfall ({value}mm) — prolonged saturation increases flood risk."

    # ── Soil Moisture ──────────────────────────────────────────────────
    elif col == "Soil_Moisture_pct":
        if value == 0:
            return "Dry soil — can absorb rain without immediate runoff."
        elif value < 50:
            return f"Soil moisture at {value}% — moderate absorption capacity remaining."
        elif value < 80:
            return f"Soil moisture at {value}% — limited absorption left, runoff likely if rain continues."
        else:
            return f"Soil is nearly saturated ({value}%) — any further rain will directly cause surface runoff and flooding."

    # ── Humidity ───────────────────────────────────────────────────────
    elif col == "Humidity_pct":
        if value < 70:
            return f"Low humidity ({value}%) — dry atmosphere, low rain probability."
        elif value < 85:
            return f"Moderate humidity ({value}%) — some atmospheric moisture present."
        else:
            return f"High humidity ({value}%) — atmosphere is heavily moisture-laden, conditions favour continued rainfall."

    # ── Is Heavy Rain ──────────────────────────────────────────────────
    elif col == "Is_Heavy_Rain":
        if value == 1:
            return "Rainfall exceeds 100mm/hr — classified as HEAVY RAIN event. Strong flood risk trigger."
        else:
            return "Rainfall is below the heavy rain threshold (100mm/hr) — no heavy rain event detected."

    # ── High Soil Moisture ─────────────────────────────────────────────
    elif col == "High_Soil_Moisture":
        if value == 1:
            return "Soil moisture flag is ON (>70%) — ground cannot absorb more water effectively."
        else:
            return "Soil moisture is within safe limits — ground has absorption capacity."

    # ── Is Monsoon ─────────────────────────────────────────────────────
    elif col == "Is_Monsoon":
        if value == 1:
            return "Currently in monsoon season (June–September) — historically the highest flood risk period in Kerala."
        else:
            return "Not in monsoon season — lower baseline flood probability for this time of year."

    # ── River Proximity ────────────────────────────────────────────────
    elif col == "River_Proximity":
        if value >= 0.7:
            return "District is close to major rivers — high exposure to river overflow during heavy rain."
        elif value >= 0.4:
            return "Moderate river proximity — some flood exposure from nearby waterways."
        else:
            return "Low river proximity — less direct exposure to river flooding."

    # ── District ───────────────────────────────────────────────────────
    elif col == "District_Encoded":
        if strong:
            return f"The district's geographic and historical flood profile has a {'strong' if strong else 'moderate'} influence on this prediction."
        else:
            return "District location has a minor influence on this specific prediction."

    # ── Month ──────────────────────────────────────────────────────────
    elif col == "Month":
        months = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
                  7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
        m_name = months.get(int(value), f"Month {int(value)}")
        if int(value) in [6,7,8,9]:
            return f"{m_name} is peak monsoon — the model treats this month as high flood risk historically."
        elif int(value) in [10,11]:
            return f"{m_name} is post-monsoon — secondary flood risk period in Kerala."
        else:
            return f"{m_name} is outside monsoon season — lower seasonal flood baseline."

    # ── Wind Speed ─────────────────────────────────────────────────────
    elif col == "Wind_Speed_kmh":
        if value > 60:
            return f"Strong winds ({value}km/h) — may indicate storm conditions, contributing to risk."
        elif value > 20:
            return f"Moderate wind speed ({value}km/h) — minor contribution to prediction."
        else:
            return f"Low wind speed ({value}km/h) — not a significant flood factor here."

    # ── Drainage / Elevation / Population ──────────────────────────────
    elif col == "Drainage_Capacity":
        return "Drainage capacity is a fixed infrastructure parameter — affects how quickly floodwater clears."
    elif col == "Low_Elevation":
        return "Low-lying terrain — water accumulates faster in flood conditions."
    elif col == "Poor_Drainage":
        return "Drainage infrastructure assumed average — no significant penalty applied."
    elif col == "Population_Density":
        return "Population density affects flood impact assessment and evacuation complexity."
    elif col == "Elevation_m":
        if value < 10:
            return f"Very low elevation ({value}m) — highly vulnerable to water accumulation."
        else:
            return f"Elevation at {value}m — some natural protection from flooding."

    # ── Pressure ───────────────────────────────────────────────────────
    elif col == "Pressure_hPa":
        if value < 1000:
            return f"Low atmospheric pressure ({value}hPa) — typically associated with storm or rain systems."
        else:
            return f"Normal atmospheric pressure ({value}hPa) — no storm system indicated."

    # ── Fallback ───────────────────────────────────────────────────────
    else:
        return f"This feature {direction} the {risk_label} risk prediction (SHAP: {shap_value:+.4f})."


# =============================================================================
# ✅ MAIN PREDICTION FUNCTION
# =============================================================================

def predict_flood_risk(district, weather, demo_mode=True, debug=False):
    """
    =========================================================================
    🤖 Flood Risk Prediction with XAI Explanation
    =========================================================================

    Input:
        district  (str)  → Kerala district name e.g. "Pathanamthitta"
        weather   (dict) → Live OpenWeather data dict
        demo_mode (bool) → If True, applies DEMO_DISTRICT_OVERRIDES
        debug     (bool) → If True, prints extra logs to console

    Output (dict):
        risk         → "High" / "Medium" / "Low"
        confidence   → {"High": 87.5, "Medium": 8.2, "Low": 4.3}
        features     → dict of all 15+ engineered feature values
        final_weather→ weather dict after any demo override applied
        explanation  → list of top-6 SHAP explanations (XAI output):
                       [{"feature": "Rainfall (1h)",
                         "value": 120,
                         "unit": "mm",
                         "shap_value": 0.42,
                         "direction": "increases_risk",
                         "bar_width": 84   ← percentage for CSS bar width
                        }, ...]
        base_value   → SHAP base value (model's average output before features)
        shap_max     → maximum absolute SHAP value (used to scale bar widths)
    """

    print("\n" + "=" * 70)
    print("🤖 FLOOD RISK PREDICTION + XAI STARTED")
    print("=" * 70)
    print("📍 District:", district)

    # ------------------------------------------------------------------
    # STEP 1: VALIDATE WEATHER INPUT
    # Prevents crashes if OpenWeather API returns incomplete data
    # ------------------------------------------------------------------

    if not weather:
        print("[ML] ⚠️  No weather data — returning Unknown")
        return {
            "risk":        "Unknown",
            "confidence":  {"Low": 0, "Medium": 0, "High": 0},
            "features":    {},
            "explanation": [],
            "error":       "Weather data missing"
        }

    # Apply safe fallback defaults so missing keys never cause KeyError
    weather = {
        "temperature": weather.get("temperature", 28),
        "humidity":    weather.get("humidity",    70),
        "pressure":    weather.get("pressure",    1010),
        "wind_speed":  weather.get("wind_speed",  2),
        "rain_1h":     weather.get("rain_1h",     0),
    }

    if debug:
        print("\n🌤 LIVE WEATHER INPUT:", weather)

    # ------------------------------------------------------------------
    # STEP 2: APPLY DEMO OVERRIDE (only for configured districts)
    # Forces extreme values so the demo shows HIGH risk predictions
    # This is transparent — final_weather in the return shows overridden values
    # ------------------------------------------------------------------

    if demo_mode and district in DEMO_DISTRICT_OVERRIDES:
        print("\n⚠  DEMO OVERRIDE ACTIVE for", district)
        override = DEMO_DISTRICT_OVERRIDES[district]
        for key, forced_value in override.items():
            original = weather.get(key, 0)
            # Only raise values, never lower them — preserves real high readings
            weather[key] = max(original, forced_value)
            print(f"   🔥 {key}: {original} → {weather[key]}")
    else:
        print("\n✅ No demo override applied for", district)

    # ------------------------------------------------------------------
    # STEP 3: FEATURE ENGINEERING
    # Convert raw weather readings into the 15 features the model was
    # trained on. Static values (elevation, river proximity etc.) are
    # fixed at training-time defaults since we don't have per-district
    # sensor data in this implementation.
    # ------------------------------------------------------------------

    # Static geographic/infrastructure features (fixed defaults)
    static_data = {
        "Elevation_m":        20,     # Average low-lying elevation
        "River_Proximity":    0.5,    # Moderate river proximity
        "Drainage_Capacity":  0.5,    # Average drainage
        "Population_Density": 1500    # Persons per sq km (Kerala avg)
    }

    month    = datetime.now().month
    rainfall = weather["rain_1h"]

    # Estimate multi-day rainfall from hourly reading
    # (Approximation — real system would use historical rain gauge data)
    rainfall_7day  = rainfall * 25    # Assumes sustained rain over 7 days
    rainfall_30day = rainfall * 80    # Assumes sustained rain over 30 days

    # Soil moisture estimated from 7-day rainfall accumulation
    # Capped at 95% — soil cannot be more than fully saturated
    soil_moisture = min(95, rainfall_7day / 8)

    # Build complete feature dictionary in the exact order the model expects
    features = {
        "District_Encoded":  district_mapping.get(district, 0),
        "Month":             month,

        # Rainfall features (primary flood predictors)
        "Daily_Rainfall_mm":  rainfall,
        "Rainfall_7day_mm":   rainfall_7day,
        "Rainfall_30day_mm":  rainfall_30day,

        # Meteorological features
        "Wind_Speed_kmh":    weather["wind_speed"] * 3.6,   # m/s → km/h
        "Temperature_C":     weather["temperature"],
        "Humidity_pct":      weather["humidity"],
        "Pressure_hPa":      weather["pressure"],

        # Static geographic features
        **static_data,

        # Derived / engineered features
        "Soil_Moisture_pct":   soil_moisture,
        "Is_Monsoon":          int(month in [6, 7, 8, 9]),   # June-September
        "Is_Heavy_Rain":       int(rainfall > 100),           # >100mm = heavy
        "Low_Elevation":       1,                             # Assume low-lying
        "Poor_Drainage":       0,                             # Assume average drainage
        "High_Soil_Moisture":  int(soil_moisture > 70),       # Saturated soil flag
    }

    # ------------------------------------------------------------------
    # STEP 4: SAFE FEATURE ALIGNMENT
    # Ensures the feature vector matches training exactly.
    # If new features were added during training that aren't in our dict,
    # they are filled with 0 rather than crashing.
    # ------------------------------------------------------------------

    missing = [col for col in feature_columns if col not in features]
    if missing:
        print(f"\n⚠  {len(missing)} missing features filled with 0: {missing}")

    # Build ordered row — must match feature_columns order exactly
    X_row = [features.get(col, 0) for col in feature_columns]
    X     = pd.DataFrame([X_row], columns=feature_columns)

    # ------------------------------------------------------------------
    # STEP 5: MODEL PREDICTION
    # Random Forest predicts both the class label and class probabilities
    # ------------------------------------------------------------------

    pred        = model.predict(X)[0]
    probs       = model.predict_proba(X)[0]
    risk_label  = target_encoder.inverse_transform([pred])[0]

    print(f"\n🚨 ML PREDICTION: {risk_label}")
    print(f"   Raw probabilities: {probs}")

    # Build confidence dict — reads class order FROM model.classes_
    # (not hardcoded) so it's correct even if class order changes
    class_labels = [target_encoder.inverse_transform([c])[0] for c in model.classes_]
    confidence   = {label: round(prob * 100, 2)
                    for label, prob in zip(class_labels, probs)}
    # Ensure all three keys always exist (prevents template errors)
    confidence.setdefault("Low",    0.0)
    confidence.setdefault("Medium", 0.0)
    confidence.setdefault("High",   0.0)

    print(f"   Class order: {class_labels}")
    print(f"   Confidence:  {confidence}")

    # ------------------------------------------------------------------
    # STEP 6: XAI — SHAP EXPLANATION
    #
    # TreeExplainer computes exact Shapley values for tree models.
    # shap_values shape: [n_classes][n_samples][n_features]
    #
    # For each feature, SHAP tells us:
    #   - How much did this feature PUSH the prediction toward this class?
    #   - Positive = pushed toward predicted class (increases risk if High)
    #   - Negative = pushed away from predicted class (decreases risk)
    #
    # We show results for the PREDICTED class only — most relevant to user.
    # ------------------------------------------------------------------

    print("\n🔍 Computing SHAP explanation...")

    try:
        # ── SHAP 0.51 COMPATIBILITY ───────────────────────────────────────
        # SHAP >= 0.46 changed TreeExplainer output format significantly.
        # Use the Explainer class (not TreeExplainer directly) which returns
        # a consistent Explanation object regardless of SHAP version.
        # This is the recommended API as of SHAP 0.41+.

        explainer_new  = shap.Explainer(model, feature_names=feature_columns)
        shap_obj       = explainer_new(X)
        # shap_obj.values shape: [n_samples, n_features, n_classes]
        # shap_obj.base_values shape: [n_samples, n_classes]

        # Get index of predicted class in model.classes_
        predicted_class_idx = list(model.classes_).index(pred)

        # Extract SHAP values for row 0, predicted class
        # shap_obj.values[0] → shape [n_features, n_classes]
        shap_matrix        = shap_obj.values[0]           # [n_features, n_classes]
        shap_for_prediction = shap_matrix[:, predicted_class_idx]  # [n_features]

        # Base value for predicted class
        base_value = float(shap_obj.base_values[0][predicted_class_idx])

        print(f"   ✅ SHAP computed via shap.Explainer "
              f"(class_idx={predicted_class_idx}, n_features={len(shap_for_prediction)})")

        # ------------------------------------------------------------------
        # Build explanation list — one entry per feature
        # ------------------------------------------------------------------

        explanation_raw = []
        for col, shap_val in zip(feature_columns, shap_for_prediction):
            raw_value = features.get(col, 0)

            explanation_raw.append({
                "feature":       FEATURE_LABELS.get(col, col),
                "col":           col,
                "value":         round(float(raw_value), 3),
                "unit":          FEATURE_UNITS.get(col, ""),
                "shap_value":    round(float(shap_val), 4),
                "direction":     "increases_risk" if shap_val > 0 else "decreases_risk",
                # Plain English sentence — shown directly on the prediction page
                "plain_english": get_plain_english(col, raw_value, float(shap_val), risk_label),
            })

        # Sort by absolute SHAP value — most impactful features first
        explanation_raw.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        # Keep only top 6 most influential features for display
        # (full list available in explanation_raw if needed for debug)
        top_explanation = explanation_raw[:6]

        # Compute bar widths as percentage of max absolute SHAP value
        # This makes the widest bar = 100% and others proportional
        shap_max = max(abs(e["shap_value"]) for e in top_explanation) if top_explanation else 1
        for e in top_explanation:
            e["bar_width"] = round((abs(e["shap_value"]) / shap_max) * 100, 1)

        print(f"   SHAP base value: {base_value:.4f}")
        print(f"   Top factors:")
        for e in top_explanation:
            direction_arrow = "↑" if e["direction"] == "increases_risk" else "↓"
            print(f"     {direction_arrow} {e['feature']}: SHAP={e['shap_value']:+.4f}  "
                  f"(value={e['value']}{e['unit']})")

    except Exception as shap_error:
        # SHAP failure is non-fatal — prediction still works without explanation
        print(f"   ⚠️  SHAP failed: {shap_error} — returning prediction without explanation")
        top_explanation = []
        base_value      = 0.0
        shap_max        = 1.0

    # ------------------------------------------------------------------
    # STEP 7: RETURN COMPLETE RESPONSE
    # All keys consumed by the Django template in ml_prediction.html
    # ------------------------------------------------------------------

    return {
        "risk":          risk_label,          # "High" / "Medium" / "Low"
        "confidence":    confidence,           # {"High": 87.5, ...}
        "features":      features,             # All 15 engineered features
        "final_weather": weather,             # Weather after demo override
        "explanation":   top_explanation,      # SHAP top-6 explanations (XAI)
        "base_value":    round(base_value, 4), # SHAP baseline probability
        "shap_max":      round(shap_max, 4),   # For scaling bars in template
        "method":        "Random Forest + SHAP TreeExplainer",
    }