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
