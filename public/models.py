from django.db import models

# Create your models here.


class public_users(models.Model):
    fullname = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15)
    district = models.CharField(max_length=50)
    password = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    email_verified = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
            db_table = 'public_users'