from django.contrib import admin
from .models import (
    Shelter, ShelterManager, ShelterStatusUpdate,
    Volunteer, SupplyLog, OverflowPredictionLog, ShelterAlert
)

@admin.register(Shelter)
class ShelterAdmin(admin.ModelAdmin):
    list_display = ["name", "district", "max_capacity", "status", "has_medical", "manager"]
    list_filter  = ["district", "status", "has_medical"]
    search_fields= ["name", "district", "address"]

@admin.register(ShelterManager)
class ShelterManagerAdmin(admin.ModelAdmin):
    list_display = ["full_name", "username", "email", "district", "is_active", "created_at"]
    list_filter  = ["is_active", "district"]

@admin.register(ShelterStatusUpdate)
class StatusUpdateAdmin(admin.ModelAdmin):
    list_display = ["shelter", "current_occupancy", "food_status", "water_status", "updated_by", "updated_at"]
    list_filter  = ["food_status", "water_status"]

@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = ["name", "shelter", "task", "status", "phone"]
    list_filter  = ["task", "status"]

@admin.register(SupplyLog)
class SupplyLogAdmin(admin.ModelAdmin):
    list_display = ["shelter", "supply_type", "quantity_available", "consumption_rate", "logged_at"]

@admin.register(OverflowPredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display = ["shelter", "risk_level", "probability", "occupancy_at", "predicted_at"]
    list_filter  = ["risk_level"]

@admin.register(ShelterAlert)
class ShelterAlertAdmin(admin.ModelAdmin):
    list_display = ["shelter", "alert_type", "is_resolved", "email_sent", "created_at"]
    list_filter  = ["alert_type", "is_resolved"]
