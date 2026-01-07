from django.urls import path
from . import views

urlpatterns = [
    path('admin_login/', views.super_admin_login, name='admin_login'),
    path('logout/', views.super_admin_logout, name='super_admin_logout'),
    path('super_admin_dashboard/', views.super_admin_dashboard, name='super_admin_dashboard'),
    path('users/', views.signup_users_list, name='signup_users_list'),
    path('api/weather/', views.admin_get_weather, name='admin_get_weather'),
    path("alerts/send/", views.send_manual_weather_alert, name="send_manual_weather_alert"),
    path("ml-flood-prediction/", views.ml_flood_prediction_view, name="ml_flood_prediction"),


]
