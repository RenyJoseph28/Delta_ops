"""
shelters/urls.py
"""
from django.urls import path
from . import views

urlpatterns = [

    # ─────────────────────────────────────────────
    # SHELTER MANAGER AUTH
    # ─────────────────────────────────────────────
    path("manager/login/",   views.shelter_manager_login,  name="shelter_manager_login"),
    path("manager/logout/",  views.shelter_manager_logout, name="shelter_manager_logout"),

    # ─────────────────────────────────────────────
    # SUPER ADMIN — SHELTER MANAGEMENT
    # ─────────────────────────────────────────────
    path("admin/shelters/",                     views.admin_shelter_dashboard,      name="admin_shelter_dashboard"),
    path("admin/shelters/add/",                 views.admin_add_shelter,            name="admin_add_shelter"),
    path("admin/shelters/<int:shelter_id>/",    views.admin_shelter_detail,         name="admin_shelter_detail"),
    path("admin/shelters/<int:shelter_id>/edit/", views.admin_edit_shelter,         name="admin_edit_shelter"),
    path("admin/shelters/recommendations/",     views.admin_shelter_recommendations,name="admin_shelter_recommendations"),
    path("admin/shelters/alerts/",              views.admin_alerts_list,            name="admin_alerts_list"),
    path("admin/shelters/alerts/<int:alert_id>/resolve/", views.admin_resolve_alert, name="admin_resolve_alert"),
    path("admin/shelters/alerts/resolve-all/",             views.admin_resolve_all_alerts, name="admin_resolve_all_alerts"),
    path("admin/managers/",                     views.admin_manage_managers,        name="admin_manage_managers"),
    path("admin/managers/add/",                 views.admin_add_manager,            name="admin_add_manager"),
    path("admin/managers/<int:manager_id>/toggle/", views.admin_toggle_manager,    name="admin_toggle_manager"),
    path("admin/shelters/train-model/",         views.admin_train_model,            name="admin_train_model"),

    # ─────────────────────────────────────────────
    # SHELTER MANAGER PORTAL
    # ─────────────────────────────────────────────
    path("manager/",                                 views.manager_dashboard,          name="manager_dashboard"),
    path("manager/shelter/<int:shelter_id>/",        views.manager_shelter_detail,     name="manager_shelter_detail"),
    path("manager/shelter/<int:shelter_id>/update/", views.manager_update_status,      name="manager_update_status"),
    path("manager/shelter/<int:shelter_id>/supply/", views.manager_log_supply,         name="manager_log_supply"),
    path("manager/shelter/<int:shelter_id>/volunteers/",     views.manager_volunteers,      name="manager_volunteers"),
    path("manager/shelter/<int:shelter_id>/volunteers/add/", views.manager_add_volunteer,   name="manager_add_volunteer"),
    path("manager/volunteer/<int:volunteer_id>/update/",     views.manager_update_volunteer, name="manager_update_volunteer"),

    # ─────────────────────────────────────────────
    # VOLUNTEER MOBILE INTERFACE
    # ─────────────────────────────────────────────
    path("volunteer/",         views.volunteer_login,        name="volunteer_login"),
    path("volunteer/logout/",  views.volunteer_logout,       name="volunteer_logout"),
    path("volunteer/update/",  views.volunteer_update,       name="volunteer_update"),
    path("volunteer/sync/",    views.volunteer_offline_sync, name="volunteer_offline_sync"),

    # ─────────────────────────────────────────────
    # PUBLIC USER — SHELTER FINDER API
    # ─────────────────────────────────────────────
    path("recommendations/",   views.public_shelter_recommendations, name="public_shelter_recommendations"),
]
