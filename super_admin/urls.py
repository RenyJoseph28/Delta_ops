from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='admin_dashboard'),
    path('admin_login/', views.super_admin_login, name='admin_login'),
    path('super_admin_dashboard/', views.super_admin_dashboard, name='super_admin_dashboard'),
]
