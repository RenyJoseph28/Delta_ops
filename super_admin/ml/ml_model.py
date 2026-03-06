# import pickle
# import numpy as np
# import os
# from django.conf import settings
# from datetime import datetime

# BASE_DIR = settings.BASE_DIR
# MODEL_DIR = os.path.join(BASE_DIR, "super_admin", "ml")

# # Load model
# with open(os.path.join(MODEL_DIR, "kerala_flood_model.pkl"), "rb") as f:
#     model = pickle.load(f)

# with open(os.path.join(MODEL_DIR, "model_config.pkl"), "rb") as f:
#     config = pickle.load(f)

# label_encoder = config["label_encoder"]
# target_encoder = config["target_encoder"]
# district_mapping = config["district_mapping"]
# feature_columns = config["feature_columns"]

# # --------------------------------------------------
# # DEMO OVERRIDE CONFIGURATION
# # --------------------------------------------------

# DEMO_DISTRICT_OVERRIDES = {
#     "Pathanamthitta": {
#         "rain_1h": 120,
#         "humidity": 92
#     },
#     "Wayanad": {
#         "rain_1h": 90,
#         "humidity": 88
#     },
#     "Idukki": {
#         "rain_1h": 75,
#         "humidity": 85
#     }
# }



# # def predict_flood_risk(district, weather):
# #     """
# #     Convert OpenWeather data → ML input → Flood risk
# #     """

# #     # Defaults / static values (same as training)
# #     static_data = {
# #         "Elevation_m": 20,
# #         "River_Proximity": 0.5,
# #         "Drainage_Capacity": 0.5,
# #         "Population_Density": 1500
# #     }

# #     month = datetime.now().month
# #     rainfall = weather.get("rain_1h", 0)
# #     rainfall_7day = rainfall * 25
# #     rainfall_30day = rainfall * 80
# #     soil_moisture = min(95, rainfall_7day / 8)

# #     features = {
# #         "District_Encoded": district_mapping.get(district, 0),
# #         "Month": month,
# #         "Daily_Rainfall_mm": rainfall,
# #         "Rainfall_7day_mm": rainfall_7day,
# #         "Rainfall_30day_mm": rainfall_30day,
# #         "Wind_Speed_kmh": weather["wind_speed"] * 3.6,
# #         "Temperature_C": weather["temperature"],
# #         "Humidity_pct": weather["humidity"],
# #         "Pressure_hPa": weather["pressure"],
# #         **static_data,
# #         "Soil_Moisture_pct": soil_moisture,
# #         "Is_Monsoon": int(month in [6,7,8,9]),
# #         "Is_Heavy_Rain": int(rainfall > 100),
# #         "Low_Elevation": 1,
# #         "Poor_Drainage": 0,
# #         "High_Soil_Moisture": int(soil_moisture > 70),
# #     }

# #     import pandas as pd

# #     X = pd.DataFrame([[features[col] for col in feature_columns]],
# #                     columns=feature_columns)

# #     pred = model.predict(X)[0]
# #     probs = model.predict_proba(X)[0]

# #     return {
# #         "risk": target_encoder.inverse_transform([pred])[0],
# #         "confidence": {
# #             "Low": round(probs[0]*100, 2),
# #             "Medium": round(probs[1]*100, 2),
# #             "High": round(probs[2]*100, 2)
# #         },
# #         "features": features
# #     }


# # def predict_flood_risk(district, weather, demo_mode=True):
# #     """
# #     Convert OpenWeather data → ML input → Flood risk
# #     demo_mode=True enables simulated extreme conditions for demo
# #     """

# #     # --------------------------------------------------
# #     # DEMO OVERRIDE (ONLY FOR PATHANAMTHITTA)
# #     # --------------------------------------------------
# #     if demo_mode and district == "Pathanamthitta":
# #         weather = weather.copy()  # do NOT mutate original
# #         weather["rain_1h"] = max(weather.get("rain_1h", 0), 120)
# #         weather["humidity"] = max(weather.get("humidity", 0), 92)

# #     # Defaults / static values (same as training)
# #     static_data = {
# #         "Elevation_m": 20,
# #         "River_Proximity": 0.5,
# #         "Drainage_Capacity": 0.5,
# #         "Population_Density": 1500
# #     }

# #     month = datetime.now().month
# #     rainfall = weather.get("rain_1h", 0)
# #     rainfall_7day = rainfall * 25
# #     rainfall_30day = rainfall * 80
# #     soil_moisture = min(95, rainfall_7day / 8)

# #     features = {
# #         "District_Encoded": district_mapping.get(district, 0),
# #         "Month": month,
# #         "Daily_Rainfall_mm": rainfall,
# #         "Rainfall_7day_mm": rainfall_7day,
# #         "Rainfall_30day_mm": rainfall_30day,
# #         "Wind_Speed_kmh": weather["wind_speed"] * 3.6,
# #         "Temperature_C": weather["temperature"],
# #         "Humidity_pct": weather["humidity"],
# #         "Pressure_hPa": weather["pressure"],
# #         **static_data,
# #         "Soil_Moisture_pct": soil_moisture,
# #         "Is_Monsoon": int(month in [6, 7, 8, 9]),
# #         "Is_Heavy_Rain": int(rainfall > 100),
# #         "Low_Elevation": 1,
# #         "Poor_Drainage": 0,
# #         "High_Soil_Moisture": int(soil_moisture > 70),
# #     }

# #     import pandas as pd

# #     X = pd.DataFrame(
# #         [[features[col] for col in feature_columns]],
# #         columns=feature_columns
# #     )

# #     pred = model.predict(X)[0]
# #     probs = model.predict_proba(X)[0]

# #     return {
# #         "risk": target_encoder.inverse_transform([pred])[0],
# #         "confidence": {
# #             "Low": round(probs[0] * 100, 2),
# #             "Medium": round(probs[1] * 100, 2),
# #             "High": round(probs[2] * 100, 2),
# #         },
# #         "features": features
# #     }


# def predict_flood_risk(district, weather, demo_mode=True, debug=False):
#     """
#     Flood Risk Prediction System (Error-Proof)

#     Steps:
#     1. Validate weather input
#     2. Apply demo override if enabled
#     3. Engineer features
#     4. Predict using trained ML model
#     5. Return risk + confidence + features
#     """

#     print("\n" + "="*70)
#     print("🤖 FLOOD RISK PREDICTION STARTED")
#     print("="*70)
#     print("📍 District:", district)

#     # --------------------------------------------------
#     # 1. VALIDATE WEATHER INPUT
#     # --------------------------------------------------
#     if not weather:
#         return {
#             "risk": "Unknown",
#             "confidence": {"Low": 0, "Medium": 0, "High": 0},
#             "error": "Weather data missing"
#         }

#     # Safe fallback values
#     weather = {
#         "temperature": weather.get("temperature", 28),
#         "humidity": weather.get("humidity", 70),
#         "pressure": weather.get("pressure", 1010),
#         "wind_speed": weather.get("wind_speed", 2),
#         "rain_1h": weather.get("rain_1h", 0)
#     }

#     if debug:
#         print("\n🌤 LIVE WEATHER INPUT")
#         print(weather)

#     # --------------------------------------------------
#     # 2. APPLY DEMO OVERRIDE IF CONFIGURED
#     # --------------------------------------------------
#     if demo_mode and district in DEMO_DISTRICT_OVERRIDES:

#         print("\n⚠ DEMO OVERRIDE ACTIVE")
#         print("-"*50)

#         override = DEMO_DISTRICT_OVERRIDES[district]

#         for key, forced_value in override.items():
#             original = weather.get(key, 0)
#             weather[key] = max(original, forced_value)

#             print(f"🔥 {key} forced from {original} → {weather[key]}")

#     else:
#         print("\n✅ No Override Applied")

#     # --------------------------------------------------
#     # 3. FEATURE ENGINEERING
#     # --------------------------------------------------
#     static_data = {
#         "Elevation_m": 20,
#         "River_Proximity": 0.5,
#         "Drainage_Capacity": 0.5,
#         "Population_Density": 1500
#     }

#     month = datetime.now().month
#     rainfall = weather["rain_1h"]

#     rainfall_7day = rainfall * 25
#     rainfall_30day = rainfall * 80
#     soil_moisture = min(95, rainfall_7day / 8)

#     features = {
#         "District_Encoded": district_mapping.get(district, 0),
#         "Month": month,
#         "Daily_Rainfall_mm": rainfall,
#         "Rainfall_7day_mm": rainfall_7day,
#         "Rainfall_30day_mm": rainfall_30day,
#         "Wind_Speed_kmh": weather["wind_speed"] * 3.6,
#         "Temperature_C": weather["temperature"],
#         "Humidity_pct": weather["humidity"],
#         "Pressure_hPa": weather["pressure"],
#         **static_data,
#         "Soil_Moisture_pct": soil_moisture,
#         "Is_Monsoon": int(month in [6, 7, 8, 9]),
#         "Is_Heavy_Rain": int(rainfall > 100),
#         "High_Soil_Moisture": int(soil_moisture > 70),
#     }

#     # --------------------------------------------------
#     # 4. MODEL PREDICTION
#     # --------------------------------------------------
#     import pandas as pd

#     X = pd.DataFrame(
#         [[features[col] for col in feature_columns]],
#         columns=feature_columns
#     )

#     pred = model.predict(X)[0]
#     probs = model.predict_proba(X)[0]

#     risk_label = target_encoder.inverse_transform([pred])[0]

#     print("\n🚨 FINAL OUTPUT")
#     print("-"*50)
#     print("Risk:", risk_label)

#     # --------------------------------------------------
#     # 5. RETURN CLEAN RESPONSE
#     # --------------------------------------------------
#     return {
#         "risk": risk_label,
#         "confidence": {
#             "Low": round(probs[0] * 100, 2),
#             "Medium": round(probs[1] * 100, 2),
#             "High": round(probs[2] * 100, 2),
#         },
#         "features": features,
#         "final_weather": weather  # ✅ send overridden weather also
#     }


import pickle
import numpy as np
import os
from django.conf import settings
from datetime import datetime


# ==========================================================
# 📌 MODEL PATH SETUP
# ==========================================================

BASE_DIR = settings.BASE_DIR
MODEL_DIR = os.path.join(BASE_DIR, "super_admin", "ml")


# ==========================================================
# 📌 LOAD TRAINED MODEL + CONFIG
# ==========================================================

with open(os.path.join(MODEL_DIR, "kerala_flood_model.pkl"), "rb") as f:
    model = pickle.load(f)

with open(os.path.join(MODEL_DIR, "model_config.pkl"), "rb") as f:
    config = pickle.load(f)

print(type(model))
# ==========================================================
# 📌 CONFIG VARIABLES
# ==========================================================

label_encoder = config["label_encoder"]
target_encoder = config["target_encoder"]
district_mapping = config["district_mapping"]
feature_columns = config["feature_columns"]


# ==========================================================
# 🌊 DEMO OVERRIDE SYSTEM (Safe + Scalable)
# ==========================================================
# Used only for demo/testing to simulate flood conditions

DEMO_DISTRICT_OVERRIDES = {
    "Pathanamthitta": {
        "rain_1h": 120,
        "humidity": 92
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


# ==========================================================
# ✅ MAIN FLOOD PREDICTION FUNCTION
# ==========================================================

def predict_flood_risk(district, weather, demo_mode=True, debug=False):
    """
    ==========================================================
    🤖 Flood Risk Prediction System
    ==========================================================

    Input:
        district (str)
        weather (dict) → Live OpenWeather data
        demo_mode (bool) → Enable override simulation
        debug (bool) → Print logs

    Output:
        risk level + confidence + features + final weather
    """

    print("\n" + "=" * 70)
    print("🤖 FLOOD RISK PREDICTION STARTED")
    print("=" * 70)
    print("📍 District:", district)

    # ----------------------------------------------------------
    # 1️⃣ WEATHER VALIDATION (Error Proof)
    # ----------------------------------------------------------

    if not weather:
        return {
            "risk": "Unknown",
            "confidence": {"Low": 0, "Medium": 0, "High": 0},
            "error": "Weather data missing"
        }

    # Safe fallback defaults (Prevents KeyErrors)
    weather = {
        "temperature": weather.get("temperature", 28),
        "humidity": weather.get("humidity", 70),
        "pressure": weather.get("pressure", 1010),
        "wind_speed": weather.get("wind_speed", 2),
        "rain_1h": weather.get("rain_1h", 0)
    }

    if debug:
        print("\n🌤 LIVE WEATHER INPUT")
        print(weather)

    # ----------------------------------------------------------
    # 2️⃣ DEMO OVERRIDE (Only for selected districts)
    # ----------------------------------------------------------

    if demo_mode and district in DEMO_DISTRICT_OVERRIDES:

        print("\n⚠ DEMO OVERRIDE ACTIVE")
        print("-" * 50)

        override = DEMO_DISTRICT_OVERRIDES[district]

        for key, forced_value in override.items():
            original = weather.get(key, 0)
            weather[key] = max(original, forced_value)

            print(f"🔥 {key} forced from {original} → {weather[key]}")

    else:
        print("\n✅ No Override Applied")

    # ----------------------------------------------------------
    # 3️⃣ STATIC + ENGINEERED FEATURES
    # ----------------------------------------------------------

    static_data = {
        "Elevation_m": 20,
        "River_Proximity": 0.5,
        "Drainage_Capacity": 0.5,
        "Population_Density": 1500
    }

    month = datetime.now().month
    rainfall = weather["rain_1h"]

    rainfall_7day = rainfall * 25
    rainfall_30day = rainfall * 80

    soil_moisture = min(95, rainfall_7day / 8)

    # ----------------------------------------------------------
    # 4️⃣ FEATURE DICTIONARY (Must match training)
    # ----------------------------------------------------------

    features = {
        "District_Encoded": district_mapping.get(district, 0),
        "Month": month,

        "Daily_Rainfall_mm": rainfall,
        "Rainfall_7day_mm": rainfall_7day,
        "Rainfall_30day_mm": rainfall_30day,

        "Wind_Speed_kmh": weather["wind_speed"] * 3.6,
        "Temperature_C": weather["temperature"],
        "Humidity_pct": weather["humidity"],
        "Pressure_hPa": weather["pressure"],

        **static_data,

        "Soil_Moisture_pct": soil_moisture,

        "Is_Monsoon": int(month in [6, 7, 8, 9]),
        "Is_Heavy_Rain": int(rainfall > 100),

        # ✅ REQUIRED FEATURES
        "Low_Elevation": 1,
        "Poor_Drainage": 0,
        "High_Soil_Moisture": int(soil_moisture > 70),
    }

    # ----------------------------------------------------------
    # 5️⃣ SAFE FEATURE ALIGNMENT (Prevents KeyError Forever)
    # ----------------------------------------------------------

    missing = [col for col in feature_columns if col not in features]

    if missing:
        print("\n⚠ Missing Features Filled With 0:")
        for m in missing:
            print("   ➜", m)

    # Fill missing automatically
    X_row = [features.get(col, 0) for col in feature_columns]

    import pandas as pd
    X = pd.DataFrame([X_row], columns=feature_columns)

    # ----------------------------------------------------------
    # 6️⃣ MODEL PREDICTION
    # ----------------------------------------------------------

    pred = model.predict(X)[0]
    probs = model.predict_proba(X)[0]

    risk_label = target_encoder.inverse_transform([pred])[0]

    print("\n🚨 FINAL ML OUTPUT")
    print("-" * 50)
    print("Risk:", risk_label)
    print("Confidence:", probs)

    # ----------------------------------------------------------
    # 7️⃣ RETURN RESPONSE
    # ----------------------------------------------------------

    # ✅ NEW — reads actual class order from the model itself
    class_labels = [target_encoder.inverse_transform([c])[0] for c in model.classes_]
    confidence = {label: round(prob * 100, 2) for label, prob in zip(class_labels, probs)}
    confidence.setdefault("Low", 0.0)
    confidence.setdefault("Medium", 0.0)
    confidence.setdefault("High", 0.0)

    print("Model class order:", class_labels)
    print("Confidence:", confidence)

    return {
        "risk": risk_label,
        "confidence": confidence,
        "features": features,
        "final_weather": weather
    }
