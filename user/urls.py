from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.profile, name='user_profile'),
    path("alerts/", views.user_alerts, name="user_alerts"),

  
]
