from django.conf import settings
import requests
from django.utils import timezone

# --- helper to call OpenWeather ---
def fetch_weather_for_city(district):
    api_key = getattr(settings, "OPENWEATHER_API_KEY", None)
    if not api_key:
        return None

    try:
        q = f"{district},IN"
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": q, "appid": api_key, "units": "metric"}
        r = requests.get(url, params=params, timeout=6)
        data = r.json()
        if r.status_code != 200:
            return None

        # Build friendly payload
        weather = {
            "city": data.get("name", district),
            "country": data.get("sys", {}).get("country", "IN"),
            "temperature": round(data["main"]["temp"], 1),
            "feels_like": round(data["main"]["feels_like"], 1),
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"],
            "wind_speed": data["wind"]["speed"],
            "clouds": data.get("clouds", {}).get("all", 0),
            "description": data["weather"][0]["description"].title(),
            "main_weather": data["weather"][0]["main"],
            "icon": data["weather"][0]["icon"],
            "icon_url": f"https://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png",
            "visibility": round(data.get("visibility", 0) / 1000, 1),  # km
            "sunrise": timezone.datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%I:%M %p"),
            "sunset": timezone.datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%I:%M %p"),
            "rain_1h": data.get("rain", {}).get("1h", 0),
            "timestamp": timezone.now().strftime("%Y-%m-%d %I:%M %p"),
        }

        # Basic rain probability estimate (OpenWeather OneCall has pop; this is heuristic)
        rain_prob = 0
        if weather["rain_1h"] > 0:
            rain_prob = 90
        elif weather["clouds"] >= 70:
            rain_prob = 60
        elif weather["clouds"] >= 40:
            rain_prob = 30
        else:
            rain_prob = 10

        weather["rain_probability"] = rain_prob
        return weather

    except Exception:
        return None

