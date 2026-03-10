"""
shelters/views.py
"""

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import make_password, check_password
from django.core.paginator import Paginator

from .models import (
    Shelter, ShelterManager, ShelterStatusUpdate,
    Volunteer, SupplyLog, OverflowPredictionLog, ShelterAlert,
    KERALA_DISTRICT_COORDS
)
from .helpers import (
    get_shelter_recommendations, get_supply_estimates,
    get_volunteer_workload, trigger_shelter_alerts
)
from .ml_overflow import predict_overflow_risk, train_overflow_model


# ═══════════════════════════════════════════════════════════════
# DECORATORS
# ═══════════════════════════════════════════════════════════════

def super_admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if "super_admin_id" not in request.session:
            print("[AUTH] ❌ Super admin not in session → redirecting to login")
            return redirect("admin_login")
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def manager_required(view_func):
    def wrapper(request, *args, **kwargs):
        if "shelter_manager_id" not in request.session:
            print("[AUTH] ❌ Manager not in session → redirecting to login")
            return redirect("shelter_manager_login")
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ═══════════════════════════════════════════════════════════════
# ① SHELTER MANAGER AUTH
# ═══════════════════════════════════════════════════════════════

def shelter_manager_login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        print(f"\n[LOGIN] Manager login attempt → username: '{username}'")

        try:
            mgr = ShelterManager.objects.get(username=username, is_active=True)
        except ShelterManager.DoesNotExist:
            print(f"[LOGIN] ❌ No active manager found with username '{username}'")
            messages.error(request, "Invalid credentials.")
            return render(request, "shelters/manager_login.html")

        if not check_password(password, mgr.password):
            print(f"[LOGIN] ❌ Wrong password for '{username}'")
            messages.error(request, "Invalid credentials.")
            return render(request, "shelters/manager_login.html")

        mgr.last_login = timezone.now()
        mgr.save()
        request.session["shelter_manager_id"]       = mgr.id
        request.session["shelter_manager_username"] = mgr.username
        request.session["shelter_manager_district"] = mgr.district

        print(f"[LOGIN] ✅ Manager '{mgr.full_name}' logged in | District: {mgr.district or 'All'}")
        return redirect("manager_dashboard")

    return render(request, "shelters/manager_login.html")


def shelter_manager_logout(request):
    username = request.session.get("shelter_manager_username", "unknown")
    print(f"[LOGOUT] Manager '{username}' logged out")
    for key in ("shelter_manager_id", "shelter_manager_username", "shelter_manager_district"):
        request.session.pop(key, None)
    return redirect("shelter_manager_login")


# ═══════════════════════════════════════════════════════════════
# ② SUPER ADMIN — SHELTER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@super_admin_required
def admin_shelter_dashboard(request):
    print("\n[SHELTER BOARD] ── Loading admin shelter dashboard ──────────────")
    shelters    = Shelter.objects.all().order_by("district", "name")
    alert_count = ShelterAlert.objects.filter(is_resolved=False).count()

    shelter_data    = []
    high_risk_count = 0

    print(f"[SHELTER BOARD] Total shelters: {shelters.count()} | Unresolved alerts: {alert_count}")

    for s in shelters:
        ml  = predict_overflow_risk(s)
        sup = get_supply_estimates(s)
        wl  = get_volunteer_workload(s)

        if ml["risk"] == "high":
            high_risk_count += 1

        food_status  = sup.get("food",  {}).get("status", "no data")
        water_status = sup.get("water", {}).get("status", "no data")
        print(f"  [{s.district}] {s.name} | "
              f"Occupancy: {s.current_occupancy}/{s.max_capacity} | "
              f"Risk: {ml['risk'].upper()} ({ml['probability']:.0%}) | "
              f"Food: {food_status} | Water: {water_status} | "
              f"Volunteers: {wl['total_active_volunteers']}")

        shelter_data.append({"shelter": s, "ml": ml, "supply": sup, "workload": wl})

    print(f"[SHELTER BOARD] High-risk shelters: {high_risk_count}")

    context = {
        "admin_username":  request.session.get("super_admin_username"),
        "shelter_data":    shelter_data,
        "total_shelters":  len(shelter_data),
        "high_risk_count": high_risk_count,
        "alert_count":     alert_count,
        "total_capacity":  sum(s.max_capacity for s in shelters),
        "total_occupancy": sum(s.current_occupancy for s in shelters),
    }
    return render(request, "shelters/admin_shelter_dashboard.html", context)


@super_admin_required
def admin_shelter_detail(request, shelter_id):
    shelter = get_object_or_404(Shelter, id=shelter_id)
    print(f"\n[SHELTER DETAIL] ── {shelter.name} (ID:{shelter_id}) ──────────")

    ml     = predict_overflow_risk(shelter)
    supply = get_supply_estimates(shelter)
    wl     = get_volunteer_workload(shelter)
    history = shelter.status_updates.order_by("-updated_at")[:20]

    print(f"[ML]       Risk: {ml['risk'].upper()} | Probability: {ml['probability']*100:.0f}% | Method: {ml['method']}")
    print(f"[SUPPLY]   Food: {supply.get('food',{}).get('status','no data')} | "
          f"Water: {supply.get('water',{}).get('status','no data')}")
    print(f"[WORKLOAD] Active volunteers: {wl['total_active_volunteers']} | "
          f"Needed: {wl['volunteers_needed']} | Status: {wl['status']}")
    print(f"[HISTORY]  Status updates on record: {history.count()}")

    # Save ML prediction to log
    OverflowPredictionLog.objects.create(
        shelter=shelter, risk_level=ml["risk"],
        probability=ml["probability"], occupancy_at=shelter.current_occupancy,
        features_used=ml.get("features"),
    )
    print(f"[PREDICTION LOG] Saved prediction entry for '{shelter.name}'")

    # Trigger FIRST, then fetch — so newly created alerts appear immediately
    print(f"[ALERT CHECK] Evaluating alert conditions for '{shelter.name}'...")
    trigger_shelter_alerts(shelter, ml_result=ml, supply_data=supply, workload_data=wl)
    alerts = shelter.alerts.filter(is_resolved=False).order_by("-created_at")
    print(f"[ALERTS]   Showing {alerts.count()} unresolved alerts")

    context = {
        "admin_username": request.session.get("super_admin_username"),
        "shelter": shelter, "ml": ml, "supply": supply,
        "workload": wl, "history": history, "alerts": alerts,
        "volunteers": shelter.volunteers.all(),
    }
    return render(request, "shelters/admin_shelter_detail.html", context)


@super_admin_required
def admin_add_shelter(request):
    managers  = ShelterManager.objects.filter(is_active=True)
    districts = list(KERALA_DISTRICT_COORDS.keys())

    if request.method == "POST":
        name     = request.POST.get("name", "").strip()
        district = request.POST.get("district")
        max_cap  = int(request.POST.get("max_capacity", 0))
        mgr_id   = request.POST.get("manager_id")

        print(f"\n[ADD SHELTER] Creating '{name}' in {district} | Capacity: {max_cap}")

        lat = request.POST.get("latitude")
        lon = request.POST.get("longitude")
        if not lat or not lon:
            lat, lon = KERALA_DISTRICT_COORDS.get(district, (0, 0))
            print(f"[ADD SHELTER] No coords provided → auto-filled from district: ({lat}, {lon})")

        shelter = Shelter.objects.create(
            name=name, district=district,
            address=request.POST.get("address", "").strip(),
            latitude=float(lat), longitude=float(lon),
            max_capacity=max_cap,
            has_medical=request.POST.get("has_medical") == "on",
            is_accessible=request.POST.get("is_accessible") == "on",
            contact_phone=request.POST.get("contact_phone", "").strip(),
            manager_id=mgr_id if mgr_id else None,
        )
        print(f"[ADD SHELTER] ✅ Created shelter ID:{shelter.id} | Manager: {mgr_id or 'None'}")
        messages.success(request, f"Shelter '{name}' added successfully.")
        return redirect("admin_shelter_dashboard")

    return render(request, "shelters/add_shelter.html", {
        "admin_username": request.session.get("super_admin_username"),
        "managers": managers, "districts": districts,
        "district_coords": json.dumps(KERALA_DISTRICT_COORDS),
    })


@super_admin_required
def admin_edit_shelter(request, shelter_id):
    shelter   = get_object_or_404(Shelter, id=shelter_id)
    managers  = ShelterManager.objects.filter(is_active=True)
    districts = list(KERALA_DISTRICT_COORDS.keys())

    if request.method == "POST":
        print(f"\n[EDIT SHELTER] Updating '{shelter.name}' (ID:{shelter_id})")
        shelter.name          = request.POST.get("name", "").strip()
        shelter.district      = request.POST.get("district")
        shelter.address       = request.POST.get("address", "").strip()
        shelter.max_capacity  = int(request.POST.get("max_capacity", 0))
        shelter.has_medical   = request.POST.get("has_medical") == "on"
        shelter.is_accessible = request.POST.get("is_accessible") == "on"
        shelter.contact_phone = request.POST.get("contact_phone", "").strip()
        shelter.status        = request.POST.get("status", "active")
        mgr_id = request.POST.get("manager_id")
        shelter.manager_id    = mgr_id if mgr_id else None
        lat = request.POST.get("latitude")
        lon = request.POST.get("longitude")
        if lat and lon:
            shelter.latitude  = float(lat)
            shelter.longitude = float(lon)
        shelter.save()
        print(f"[EDIT SHELTER] ✅ '{shelter.name}' updated | Status: {shelter.status}")
        messages.success(request, "Shelter updated.")
        return redirect("admin_shelter_detail", shelter_id=shelter_id)

    return render(request, "shelters/edit_shelter.html", {
        "admin_username": request.session.get("super_admin_username"),
        "shelter": shelter, "managers": managers, "districts": districts,
        "district_coords": json.dumps(KERALA_DISTRICT_COORDS),
    })


@super_admin_required
def admin_manage_managers(request):
    managers = ShelterManager.objects.all().order_by("-created_at")
    print(f"[MANAGERS] Listing {managers.count()} shelter managers")
    return render(request, "shelters/manage_managers.html", {
        "admin_username": request.session.get("super_admin_username"),
        "managers": managers,
    })


@super_admin_required
def admin_add_manager(request):
    districts = list(KERALA_DISTRICT_COORDS.keys())
    if request.method == "POST":
        raw_password = request.POST.get("password", "")
        full_name    = request.POST.get("full_name", "").strip()
        username     = request.POST.get("username", "").strip()
        email        = request.POST.get("email", "").strip()
        district     = request.POST.get("district")

        print(f"\n[ADD MANAGER] Creating '{full_name}' | Username: '{username}' | Email: '{email}' | District: '{district or 'All'}'")

        mgr = ShelterManager.objects.create(
            full_name=full_name, username=username,
            password=make_password(raw_password), email=email,
            phone=request.POST.get("phone", "").strip(), district=district,
        )
        print(f"[ADD MANAGER] ✅ Manager created with ID:{mgr.id}")

        print(f"[EMAIL] Attempting to send credentials to '{email}'...")
        email_sent = _send_manager_credentials_email(mgr, raw_password, request)

        if email_sent:
            print(f"[EMAIL] ✅ Credentials email sent successfully to '{email}'")
            messages.success(request, f"Manager '{mgr.full_name}' created and credentials emailed to {mgr.email}.")
        else:
            print(f"[EMAIL] ❌ Failed to send email to '{email}' — share credentials manually")
            messages.warning(request, f"Manager '{mgr.full_name}' created but email failed. Share credentials manually.")

        return redirect("admin_manage_managers")

    return render(request, "shelters/add_manager.html", {
        "admin_username": request.session.get("super_admin_username"),
        "districts": districts,
    })


def _send_manager_credentials_email(mgr, raw_password, request):
    import logging
    logger = logging.getLogger(__name__)

    login_url     = request.build_absolute_uri("/shelters/manager/login/")
    volunteer_url = request.build_absolute_uri("/shelters/volunteer/")

    subject = "Your Shelter Manager Account — Delta Ops Kerala Flood System"
    body = f"""Dear {mgr.full_name},

Your Shelter Manager account has been created on the Kerala Flood Relief System (Delta Ops).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR LOGIN CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Login URL  : {login_url}
Username   : {mgr.username}
Password   : {raw_password}
District   : {mgr.district or "All Districts"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR RESPONSIBILITIES:
  • Monitor real-time occupancy and status of your assigned shelters
  • Log food and water supply levels regularly
  • Manage volunteers and their task assignments
  • Submit status updates whenever conditions change

IMPORTANT:
  • Do not share your credentials with anyone.
  • For volunteer PIN login, direct volunteers to: {volunteer_url}

If you have any issues logging in, contact the system administrator.

— Kerala Flood Relief System
  Delta Ops Administration
"""

    try:
        from django.core.mail import send_mail
        from django.conf import settings
        print(f"[EMAIL] Connecting to mail server | From: {settings.DEFAULT_FROM_EMAIL} | To: {mgr.email}")
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [mgr.email], fail_silently=False)
        return True
    except Exception as e:
        logger.error("Failed to send credentials email to %s: %s", mgr.email, e)
        print(f"[EMAIL] ❌ Exception while sending: {e}")
        return False


@super_admin_required
def admin_toggle_manager(request, manager_id):
    mgr = get_object_or_404(ShelterManager, id=manager_id)
    mgr.is_active = not mgr.is_active
    mgr.save()
    status = "ACTIVATED" if mgr.is_active else "DEACTIVATED"
    print(f"[MANAGER] {status} → '{mgr.full_name}' (ID:{mgr.id})")
    messages.success(request, f"Manager '{mgr.full_name}' {'activated' if mgr.is_active else 'deactivated'}.")
    return redirect("admin_manage_managers")


@super_admin_required
def admin_resolve_alert(request, alert_id):
    alert = get_object_or_404(ShelterAlert, id=alert_id)
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.save()
    print(f"[ALERT] ✅ Resolved | ID:{alert_id} | Type: {alert.alert_type} | Shelter: {alert.shelter.name}")
    return JsonResponse({"success": True})


@super_admin_required
@require_POST
def admin_resolve_all_alerts(request):
    """Resolve all unresolved alerts — optionally filtered by shelter_id."""
    shelter_id = request.POST.get("shelter_id")
    qs = ShelterAlert.objects.filter(is_resolved=False)
    if shelter_id:
        qs = qs.filter(shelter_id=shelter_id)
    count = qs.count()
    qs.update(is_resolved=True, resolved_at=timezone.now())
    print(f"[ALERT] 🧹 Bulk resolved {count} alerts | shelter_id={shelter_id or 'ALL'}")
    return JsonResponse({"success": True, "resolved_count": count})


@super_admin_required
def admin_train_model(request):
    print("\n[ML] 🤖 Starting ML overflow model training...")
    result = train_overflow_model()
    if result:
        print("[ML] ✅ Model trained and saved successfully → overflow_model.pkl")
        messages.success(request, "ML model trained successfully.")
    else:
        print("[ML] ⚠️  Not enough data to train (need 20+ status update records)")
        messages.warning(request, "Not enough data to train the model yet.")
    return redirect("admin_shelter_dashboard")


@super_admin_required
def admin_shelter_recommendations(request):
    districts         = list(KERALA_DISTRICT_COORDS.keys())
    recommendations   = []
    selected_district = request.GET.get("district")
    origin_lat        = request.GET.get("lat")
    origin_lon        = request.GET.get("lon")
    is_ajax           = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if origin_lat and origin_lon:
        print(f"\n[RECOMMEND] Origin: ({origin_lat}, {origin_lon}) | District: {selected_district or 'All'} | AJAX: {is_ajax}")
        recommendations = get_shelter_recommendations(
            float(origin_lat), float(origin_lon),
            district=selected_district, top_n=3,
        )
        print(f"[RECOMMEND] {len(recommendations)} shelters found:")
        for i, r in enumerate(recommendations, 1):
            print(f"  {i}. {r['shelter'].name} | {r['distance_km']}km | {r['occupancy_pct']}% full | Score: {r['composite']}")

    # Serialize recommendations for AJAX or template JSON
    reco_json = json.dumps([{
        "shelter_id":   r["shelter"].id,
        "name":         r["shelter"].name,
        "district":     r["shelter"].district,
        "latitude":     float(r["shelter"].latitude),
        "longitude":    float(r["shelter"].longitude),
        "distance_km":  r["distance_km"],
        "free_slots":   r["free_slots"],
        "occupancy_pct":r["occupancy_pct"],
        "composite":    r["composite"],
        "accessible":   r["accessible"],
        "has_medical":  r["has_medical"],
    } for r in recommendations])

    # AJAX call from the map page JS → return JSON only
    if is_ajax:
        return JsonResponse({"recommendations": json.loads(reco_json)})

    return render(request, "shelters/recommendations.html", {
        "admin_username":      request.session.get("super_admin_username"),
        "districts":           districts,
        "district_coords":     json.dumps(KERALA_DISTRICT_COORDS),
        "recommendations":     recommendations,
        "recommendations_json": reco_json,
        "selected_district":   selected_district,
        "origin_lat":          origin_lat,
        "origin_lon":          origin_lon,
    })


@super_admin_required
def admin_alerts_list(request):
    alerts   = ShelterAlert.objects.filter(is_resolved=False).order_by("-created_at")
    resolved = ShelterAlert.objects.filter(is_resolved=True).order_by("-resolved_at")[:20]
    print(f"[ALERTS LIST] Active: {alerts.count()} | Recently resolved: {resolved.count()}")
    return render(request, "shelters/alerts_list.html", {
        "admin_username": request.session.get("super_admin_username"),
        "alerts": alerts, "resolved": resolved,
    })


# ═══════════════════════════════════════════════════════════════
# ③ SHELTER MANAGER DASHBOARD
# ═══════════════════════════════════════════════════════════════

@manager_required
def manager_dashboard(request):
    mgr_id   = request.session["shelter_manager_id"]
    mgr      = get_object_or_404(ShelterManager, id=mgr_id)
    shelters = Shelter.objects.filter(manager=mgr)

    print(f"\n[MANAGER DASHBOARD] ── '{mgr.full_name}' ──────────────────────")
    print(f"[MANAGER DASHBOARD] Shelters assigned: {shelters.count()}")

    shelter_data = []
    for s in shelters:
        ml  = predict_overflow_risk(s)
        sup = get_supply_estimates(s)
        wl  = get_volunteer_workload(s)

        print(f"  → {s.name} | Occupancy: {s.current_occupancy}/{s.max_capacity} | "
              f"Risk: {ml['risk'].upper()} | "
              f"Food: {sup.get('food',{}).get('status','?')} | "
              f"Water: {sup.get('water',{}).get('status','?')} | "
              f"Volunteers: {wl['total_active_volunteers']}")

        print(f"    [ALERT CHECK] Evaluating conditions for '{s.name}'...")
        trigger_shelter_alerts(shelter=s, ml_result=ml, supply_data=sup, workload_data=wl)

        shelter_data.append({"shelter": s, "ml": ml, "supply": sup, "workload": wl})

    alert_count = ShelterAlert.objects.filter(shelter__manager=mgr, is_resolved=False).count()
    print(f"[MANAGER DASHBOARD] Total unresolved alerts: {alert_count}")

    return render(request, "shelters/manager_dashboard.html", {
        "manager": mgr, "shelter_data": shelter_data, "alert_count": alert_count,
    })


@manager_required
def manager_shelter_detail(request, shelter_id):
    mgr_id  = request.session["shelter_manager_id"]
    shelter = get_object_or_404(Shelter, id=shelter_id, manager_id=mgr_id)

    print(f"\n[MANAGER DETAIL] ── '{request.session['shelter_manager_username']}' → {shelter.name} ──")

    ml     = predict_overflow_risk(shelter)
    supply = get_supply_estimates(shelter)
    wl     = get_volunteer_workload(shelter)
    history = shelter.status_updates.order_by("-updated_at")[:10]

    print(f"[ML]       Risk: {ml['risk'].upper()} | Probability: {ml['probability']*100:.0f}%")
    print(f"[SUPPLY]   Food: {supply.get('food',{}).get('status','no data')} | Water: {supply.get('water',{}).get('status','no data')}")
    print(f"[WORKLOAD] {wl['total_active_volunteers']} active volunteers | Status: {wl['status']}")

    # Trigger FIRST, fetch AFTER so new alerts appear immediately
    trigger_shelter_alerts(shelter, ml_result=ml, supply_data=supply, workload_data=wl)
    alerts = shelter.alerts.filter(is_resolved=False).order_by("-created_at")
    print(f"[ALERTS]   {alerts.count()} unresolved alerts")

    return render(request, "shelters/manager_shelter_detail.html", {
        "manager":    get_object_or_404(ShelterManager, id=mgr_id),
        "shelter":    shelter, "ml": ml, "supply": supply, "workload": wl,
        "history":    history, "latest": shelter.latest_status,
        "alerts":     alerts,
        "volunteers": shelter.volunteers.all(),
    })


@manager_required
@require_POST
def manager_update_status(request, shelter_id):
    mgr_id  = request.session["shelter_manager_id"]
    shelter = get_object_or_404(Shelter, id=shelter_id, manager_id=mgr_id)

    occupancy = request.POST.get("current_occupancy", 0)
    food      = request.POST.get("food_status", "ok")
    water     = request.POST.get("water_status", "ok")
    medical   = request.POST.get("medical_support") == "on"

    print(f"\n[STATUS UPDATE] Manager '{request.session['shelter_manager_username']}' → '{shelter.name}'")
    print(f"  Occupancy: {occupancy}/{shelter.max_capacity} | Food: {food} | Water: {water} | Medical: {medical}")

    _save_status_update(request, shelter, updated_by=request.session["shelter_manager_username"])
    print(f"[STATUS UPDATE] ✅ Saved to DB")

    messages.success(request, "Shelter status updated.")
    return redirect("manager_shelter_detail", shelter_id=shelter_id)


@manager_required
@require_POST
def manager_log_supply(request, shelter_id):
    mgr_id      = request.session["shelter_manager_id"]
    shelter     = get_object_or_404(Shelter, id=shelter_id, manager_id=mgr_id)
    supply_type = request.POST.get("supply_type")
    quantity    = float(request.POST.get("quantity", 0))
    rate        = float(request.POST.get("consumption_rate", 0))

    print(f"\n[SUPPLY LOG] '{shelter.name}' | Type: {supply_type} | Qty: {quantity} | Rate: {rate}/person/day")

    SupplyLog.objects.create(
        shelter=shelter, supply_type=supply_type,
        quantity_available=quantity, consumption_rate=rate,
        logged_by=request.session["shelter_manager_username"],
    )

    if rate > 0 and shelter.current_occupancy > 0:
        days = round(quantity / (rate * shelter.current_occupancy), 1)
        print(f"[SUPPLY LOG] ✅ Saved | Estimated days remaining: {days}d")
    else:
        print(f"[SUPPLY LOG] ✅ Saved | (no rate/occupancy — cannot estimate days)")

    messages.success(request, "Supply log saved.")
    return redirect("manager_shelter_detail", shelter_id=shelter_id)


@manager_required
def manager_volunteers(request, shelter_id):
    mgr_id     = request.session["shelter_manager_id"]
    shelter    = get_object_or_404(Shelter, id=shelter_id, manager_id=mgr_id)
    volunteers = shelter.volunteers.all()
    print(f"[VOLUNTEERS] '{shelter.name}' | Total volunteers: {volunteers.count()}")
    return render(request, "shelters/volunteers.html", {
        "manager": get_object_or_404(ShelterManager, id=mgr_id),
        "shelter": shelter, "volunteers": volunteers,
        "task_choices": Volunteer.TASK_CHOICES,
    })


@manager_required
@require_POST
def manager_add_volunteer(request, shelter_id):
    mgr_id  = request.session["shelter_manager_id"]
    shelter = get_object_or_404(Shelter, id=shelter_id, manager_id=mgr_id)
    name    = request.POST.get("name", "").strip()
    pin     = request.POST.get("pin", "").strip()
    task    = request.POST.get("task", "general")

    print(f"\n[ADD VOLUNTEER] '{name}' → '{shelter.name}' | Task: {task} | PIN: {pin}")

    Volunteer.objects.create(
        shelter=shelter, name=name,
        phone=request.POST.get("phone", "").strip(),
        pin=pin, task=task,
        shift_start=request.POST.get("shift_start") or None,
        shift_end=request.POST.get("shift_end") or None,
    )
    print(f"[ADD VOLUNTEER] ✅ Volunteer '{name}' added successfully")
    messages.success(request, "Volunteer added.")
    return redirect("manager_volunteers", shelter_id=shelter_id)


@manager_required
@require_POST
def manager_update_volunteer(request, volunteer_id):
    vol        = get_object_or_404(Volunteer, id=volunteer_id)
    old_task   = vol.task
    old_status = vol.status
    vol.task   = request.POST.get("task", vol.task)
    vol.status = request.POST.get("status", vol.status)
    vol.save()
    print(f"[VOLUNTEER UPDATE] '{vol.name}' | Task: {old_task}→{vol.task} | Status: {old_status}→{vol.status}")
    return JsonResponse({"success": True})


# ═══════════════════════════════════════════════════════════════
# ④ VOLUNTEER MOBILE INTERFACE
# ═══════════════════════════════════════════════════════════════

def volunteer_login(request):
    if request.method == "POST":
        pin  = request.POST.get("pin", "").strip()
        name = request.POST.get("name", "").strip()

        print(f"\n[VOLUNTEER LOGIN] Attempt → Name: '{name}' | PIN: '{pin}'")

        try:
            vol = Volunteer.objects.get(pin=pin, name__iexact=name)
        except Volunteer.DoesNotExist:
            print(f"[VOLUNTEER LOGIN] ❌ No match for name='{name}' pin='{pin}'")
            messages.error(request, "Invalid name or PIN.")
            return render(request, "shelters/volunteer_login.html")

        request.session["volunteer_id"]      = vol.id
        request.session["volunteer_name"]    = vol.name
        request.session["volunteer_shelter"] = vol.shelter_id
        print(f"[VOLUNTEER LOGIN] ✅ '{vol.name}' logged in | Shelter: '{vol.shelter.name}' | Task: {vol.task}")
        return redirect("volunteer_update")

    return render(request, "shelters/volunteer_login.html")


def volunteer_logout(request):
    name = request.session.get("volunteer_name", "unknown")
    print(f"[VOLUNTEER LOGOUT] '{name}' logged out")
    for k in ("volunteer_id", "volunteer_name", "volunteer_shelter"):
        request.session.pop(k, None)
    return redirect("volunteer_login")


def volunteer_update(request):
    if "volunteer_id" not in request.session:
        print("[VOLUNTEER] No session found → redirecting to login")
        return redirect("volunteer_login")

    vol     = get_object_or_404(Volunteer, id=request.session["volunteer_id"])
    shelter = vol.shelter

    if request.method == "POST":
        occupancy = request.POST.get("current_occupancy", 0)
        food      = request.POST.get("food_status", "ok")
        water     = request.POST.get("water_status", "ok")
        medical   = request.POST.get("medical_support") == "on"

        print(f"\n[VOLUNTEER UPDATE] '{vol.name}' → '{shelter.name}'")
        print(f"  Occupancy: {occupancy}/{shelter.max_capacity} | Food: {food} | Water: {water} | Medical: {medical}")

        _save_status_update(request, shelter, updated_by=f"Volunteer: {vol.name}")
        print(f"[VOLUNTEER UPDATE] ✅ Status saved to DB")

        messages.success(request, "✅ Status updated successfully!")
        return redirect("volunteer_update")

    print(f"[VOLUNTEER] '{vol.name}' loading update form for '{shelter.name}'")
    return render(request, "shelters/volunteer_update.html", {
        "volunteer": vol, "shelter": shelter, "latest": shelter.latest_status,
    })


@require_POST
def volunteer_offline_sync(request):
    print("\n[OFFLINE SYNC] Received offline sync request")
    try:
        data      = json.loads(request.body)
        volunteer = get_object_or_404(Volunteer, id=data["volunteer_id"], pin=data["pin"])
        shelter   = volunteer.shelter
        updates   = data.get("updates", [])

        print(f"[OFFLINE SYNC] Volunteer: '{volunteer.name}' | Shelter: '{shelter.name}' | Pending updates: {len(updates)}")

        for i, u in enumerate(updates, 1):
            ShelterStatusUpdate.objects.create(
                shelter=shelter,
                current_occupancy=u.get("occupancy", 0),
                food_status=u.get("food_status", "ok"),
                water_status=u.get("water_status", "ok"),
                medical_support=u.get("medical_support", False),
                notes=u.get("notes", ""),
                updated_by=f"Volunteer: {volunteer.name} (offline sync)",
                updated_at=u.get("timestamp", timezone.now()),
                is_synced=False,
            )
            print(f"  [{i}/{len(updates)}] Occupancy: {u.get('occupancy')} | "
                  f"Food: {u.get('food_status')} | Water: {u.get('water_status')}")

        print(f"[OFFLINE SYNC] ✅ Synced {len(updates)} updates for '{shelter.name}'")
        return JsonResponse({"success": True, "synced": len(updates)})
    except Exception as e:
        print(f"[OFFLINE SYNC] ❌ Error: {e}")
        return JsonResponse({"error": str(e)}, status=400)


# ═══════════════════════════════════════════════════════════════
# SHARED UTILITY
# ═══════════════════════════════════════════════════════════════

def _save_status_update(request, shelter, updated_by: str):
    ShelterStatusUpdate.objects.create(
        shelter=shelter,
        current_occupancy=int(request.POST.get("current_occupancy", 0)),
        food_status=request.POST.get("food_status", "ok"),
        water_status=request.POST.get("water_status", "ok"),
        medical_support=request.POST.get("medical_support") == "on",
        notes=request.POST.get("notes", "").strip(),
        updated_by=updated_by,
    )


# ═══════════════════════════════════════════════════════════════
# ⑤  PUBLIC — SHELTER FINDER  (used by logged-in public users)
# ═══════════════════════════════════════════════════════════════


def public_shelter_recommendations(request):
    """
    GET /shelters/recommendations/?lat=<float>&lon=<float>
    Called via AJAX from the user-facing shelter finder page.
    Returns top-3 shelters with route geometry + turn-by-turn steps.
    No admin/manager auth required — only a valid public user session.
    """
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not is_ajax:
        return redirect("shelter_finder")

    try:
        lat = float(request.GET.get("lat", 0))
        lon = float(request.GET.get("lon", 0))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    if lat == 0 and lon == 0:
        return JsonResponse({"error": "Coordinates required"}, status=400)

    print(f"\n[PUBLIC RECOMMEND] Origin: ({lat}, {lon})")

    results = get_shelter_recommendations(lat, lon, district=None, top_n=3)

    shelter_list = []
    for r in results:
        s = r["shelter"]
        geometry, steps = _fetch_osrm_route(lat, lon, float(s.latitude), float(s.longitude))

        shelter_list.append({
            "name":           s.name,
            "address":        s.address or "",
            "district":       s.district,
            "lat":            float(s.latitude),
            "lon":            float(s.longitude),
            "distance_km":    r["distance_km"],
            "duration_min":   r.get("duration_min"),
            "free_slots":     r["free_slots"],
            "occupancy_pct":  r["occupancy_pct"],
            "composite":      r["composite"],
            "has_medical":    r["has_medical"],
            "is_accessible":  r["accessible"],
            "contact_phone":  s.contact_phone or "",
            "route_geometry": geometry,
            "route_steps":    steps,
        })

    print(f"[PUBLIC RECOMMEND] Returning {len(shelter_list)} shelters to user")
    return JsonResponse({"shelters": shelter_list})


def _fetch_osrm_route(origin_lat, origin_lon, dest_lat, dest_lon):
    """
    Fetch full OSRM route: geometry (for Leaflet polyline) + steps (turn-by-turn).
    Returns (geometry_dict | None, steps_list).
    """
    import urllib.request
    import urllib.error
    import json as _json

    try:
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{float(origin_lon)},{float(origin_lat)};"
            f"{float(dest_lon)},{float(dest_lat)}"
            f"?overview=full&geometries=geojson&steps=true"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DeltaOps/1.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode("utf-8"))

        if data.get("code") != "Ok":
            return None, []

        route    = data["routes"][0]
        geometry = route.get("geometry")

        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                maneuver  = step.get("maneuver", {})
                m_type    = maneuver.get("type", "")
                m_mod     = maneuver.get("modifier", "")
                road_name = step.get("name", "") or step.get("ref", "") or "road"

                if m_type == "turn":
                    key = f"turn-{m_mod}".replace(" ", "-") if m_mod else "straight"
                elif m_type in ("depart", "arrive", "roundabout", "merge", "fork"):
                    key = m_type
                else:
                    key = "straight"

                if m_type == "depart":
                    instruction = f"Head towards {road_name}"
                elif m_type == "arrive":
                    instruction = "Arrive at destination"
                elif m_type == "turn" and m_mod:
                    instruction = f"Turn {m_mod} onto {road_name}"
                elif m_type == "roundabout":
                    exit_n = maneuver.get("exit", "")
                    instruction = f"Take exit {exit_n} at roundabout" if exit_n else "Enter roundabout"
                else:
                    instruction = f"Continue on {road_name}"

                steps.append({
                    "maneuver":    key,
                    "instruction": instruction,
                    "name":        road_name,
                    "distance":    step.get("distance", 0),
                })

        return geometry, steps

    except urllib.error.HTTPError as e:
        print(f"  [OSRM ROUTE] HTTP {e.code} — no geometry/steps")
    except urllib.error.URLError:
        print(f"  [OSRM ROUTE] URL Error — no geometry/steps")
    except Exception as e:
        print(f"  [OSRM ROUTE] Error: {e}")

    return None, []