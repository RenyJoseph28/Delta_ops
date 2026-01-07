from django.conf import settings
import requests
from django.utils import timezone

from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta

from public.models import public_users
from super_admin.models import weather_alerts
from django.conf import settings

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


# --- helper to calculate risk level based on weather ---
def calculate_risk(weather):
    rain = weather.get("rain_probability", 0)
    humidity = weather.get("humidity", 0)

    if rain >= 60 or humidity >= 85:
        return "high"
    elif rain >= 30:
        return "moderate"
    return "low"


# --- helper to send weather alert emails ---
# def send_weather_email_alert(district, weather):
#     risk = calculate_risk(weather)

#     # Do not alert for low risk
#     if risk == "low":
#         return

#     # Cooldown: do not send same alert within 3 hours
#     recent_alert = weather_alerts.objects.filter(
#         district=district,
#         risk_level=risk,
#         sent_at__gte=timezone.now() - timedelta(hours=3)
#     ).exists()

#     if recent_alert:
#         return

#     # Get users in that district
#     users = public_users.objects.filter(
#         district__iexact=district,
#         is_active=True
#     )

#     if not users.exists():
#         return

#     # Email content
#     subject = f"⚠️ Weather Alert for {district}"

#     if risk == "high":
#         message = (
#             f"🚨 HIGH RISK WEATHER ALERT 🚨\n\n"
#             f"Severe weather conditions are expected in {district}.\n"
#             f"Rain Probability: {weather['rain_probability']}%\n"
#             f"Humidity: {weather['humidity']}%\n\n"
#             f"Please avoid unnecessary travel and stay safe.\n\n"
#             f"- Delta Ops"
#         )
#     else:
#         message = (
#             f"⚠️ MODERATE WEATHER ALERT ⚠️\n\n"
#             f"Heavy rain is expected in {district}.\n"
#             f"Rain Probability: {weather['rain_probability']}%\n\n"
#             f"Please stay alert.\n\n"
#             f"- Delta Ops"
#         )

#     recipient_list = list(users.values_list("email", flat=True))

#     send_mail(
#         subject,
#         message,
#         settings.DEFAULT_FROM_EMAIL,
#         recipient_list,
#         fail_silently=True
#     )

#     # Save alert log
#     weather_alerts.objects.create(
#         district=district,
#         risk_level=risk
#     )


def send_weather_email_alert(district, weather):
    risk = calculate_risk(weather)

    # Do not alert for low risk
    if risk == "low":
        return

    # ----------------------------------------
    # Cooldown logic (disabled in test mode)
    # ----------------------------------------
    if not getattr(settings, "ALERT_TEST_MODE", False):
        recent_alert = weather_alerts.objects.filter(
            district=district,
            risk_level=risk,
            sent_at__gte=timezone.now() - timedelta(hours=3)
        ).exists()

        if recent_alert:
            return

    # Get users in that district
    users = public_users.objects.filter(
        district__iexact=district,
        is_active=True
    )

    # FOR TESTING: send to admin if no users
    recipient_list = list(users.values_list("email", flat=True))
    if not recipient_list:
        recipient_list = [settings.DEFAULT_FROM_EMAIL]

    subject = f"⚠️ Weather Alert for {district}"

    if risk == "high":
        message = (
            f"🚨 HIGH RISK WEATHER ALERT 🚨\n\n"
            f"Severe weather conditions are expected in {district}.\n"
            f"Rain Probability: {weather['rain_probability']}%\n"
            f"Humidity: {weather['humidity']}%\n\n"
            f"Please avoid unnecessary travel and stay safe.\n\n"
            f"- Delta Ops"
        )
    else:
        message = (
            f"⚠️ MODERATE WEATHER ALERT ⚠️\n\n"
            f"Heavy rain is expected in {district}.\n"
            f"Rain Probability: {weather['rain_probability']}%\n\n"
            f"Please stay alert.\n\n"
            f"- Delta Ops"
        )

    sent = send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        fail_silently=False
    )

    print(f"EMAIL SENT | District={district} | Risk={risk} | Count={sent}")

    weather_alerts.objects.create(
        district=district,
        risk_level=risk
    )
