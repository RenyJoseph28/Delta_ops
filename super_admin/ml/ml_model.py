import pickle
import numpy as np
import os
from django.conf import settings
from datetime import datetime

BASE_DIR = settings.BASE_DIR
MODEL_DIR = os.path.join(BASE_DIR, "super_admin", "ml")

# Load model
with open(os.path.join(MODEL_DIR, "kerala_flood_model.pkl"), "rb") as f:
    model = pickle.load(f)

with open(os.path.join(MODEL_DIR, "model_config.pkl"), "rb") as f:
    config = pickle.load(f)

label_encoder = config["label_encoder"]
target_encoder = config["target_encoder"]
district_mapping = config["district_mapping"]
feature_columns = config["feature_columns"]


# def predict_flood_risk(district, weather):
#     """
#     Convert OpenWeather data → ML input → Flood risk
#     """

#     # Defaults / static values (same as training)
#     static_data = {
#         "Elevation_m": 20,
#         "River_Proximity": 0.5,
#         "Drainage_Capacity": 0.5,
#         "Population_Density": 1500
#     }

#     month = datetime.now().month
#     rainfall = weather.get("rain_1h", 0)
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
#         "Is_Monsoon": int(month in [6,7,8,9]),
#         "Is_Heavy_Rain": int(rainfall > 100),
#         "Low_Elevation": 1,
#         "Poor_Drainage": 0,
#         "High_Soil_Moisture": int(soil_moisture > 70),
#     }

#     import pandas as pd

#     X = pd.DataFrame([[features[col] for col in feature_columns]],
#                     columns=feature_columns)

#     pred = model.predict(X)[0]
#     probs = model.predict_proba(X)[0]

#     return {
#         "risk": target_encoder.inverse_transform([pred])[0],
#         "confidence": {
#             "Low": round(probs[0]*100, 2),
#             "Medium": round(probs[1]*100, 2),
#             "High": round(probs[2]*100, 2)
#         },
#         "features": features
#     }


def predict_flood_risk(district, weather, demo_mode=True):
    """
    Convert OpenWeather data → ML input → Flood risk
    demo_mode=True enables simulated extreme conditions for demo
    """

    # --------------------------------------------------
    # DEMO OVERRIDE (ONLY FOR PATHANAMTHITTA)
    # --------------------------------------------------
    if demo_mode and district == "Pathanamthitta":
        weather = weather.copy()  # do NOT mutate original
        weather["rain_1h"] = max(weather.get("rain_1h", 0), 120)
        weather["humidity"] = max(weather.get("humidity", 0), 92)

    # Defaults / static values (same as training)
    static_data = {
        "Elevation_m": 20,
        "River_Proximity": 0.5,
        "Drainage_Capacity": 0.5,
        "Population_Density": 1500
    }

    month = datetime.now().month
    rainfall = weather.get("rain_1h", 0)
    rainfall_7day = rainfall * 25
    rainfall_30day = rainfall * 80
    soil_moisture = min(95, rainfall_7day / 8)

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
        "Low_Elevation": 1,
        "Poor_Drainage": 0,
        "High_Soil_Moisture": int(soil_moisture > 70),
    }

    import pandas as pd

    X = pd.DataFrame(
        [[features[col] for col in feature_columns]],
        columns=feature_columns
    )

    pred = model.predict(X)[0]
    probs = model.predict_proba(X)[0]

    return {
        "risk": target_encoder.inverse_transform([pred])[0],
        "confidence": {
            "Low": round(probs[0] * 100, 2),
            "Medium": round(probs[1] * 100, 2),
            "High": round(probs[2] * 100, 2),
        },
        "features": features
    }
