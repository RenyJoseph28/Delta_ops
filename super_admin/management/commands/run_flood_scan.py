from django.core.management.base import BaseCommand
from super_admin.helpers import fetch_weather_for_city, send_weather_email_alert
from super_admin.ml.ml_model import predict_flood_risk

DISTRICTS = [
 "Alappuzha","Ernakulam","Idukki","Kannur","Kasaragod","Kollam",
 "Kottayam","Kozhikode","Malappuram","Palakkad","Pathanamthitta",
 "Thiruvananthapuram","Thrissur","Wayanad"
]

class Command(BaseCommand):
    help = "Automatic ML flood monitoring"

    def handle(self, *args, **kwargs):
        for d in DISTRICTS:
            weather = fetch_weather_for_city(d)
            if not weather:
                continue

            ml = predict_flood_risk(d, weather)

            if ml["risk"] == "High":
                send_weather_email_alert(d, weather)

        self.stdout.write("✔ Flood scan completed")
