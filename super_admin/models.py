from django.db import models

# Create your models here.
class super_admin(models.Model):
    username = models.CharField(max_length = 200, null=True)
    password = models.CharField(max_length = 200, null=True)
    email = models.EmailField(max_length=120)
    last_login = models.CharField(max_length = 50, null=True)
    is_active = models.IntegerField(null=True)
    date_joined = models.DateTimeField()
    class Meta:
        db_table = 'super_admin'


class weather_alerts(models.Model):
    district = models.CharField(max_length=50)
    risk_level = models.CharField(max_length=20)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weather_alerts"

    def __str__(self):
        return f"{self.district} - {self.risk_level}"

