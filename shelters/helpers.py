"""
shelters/helpers.py
────────────────────────────────────────────────────────────────
Helper utilities:
  - Shelter recommendation engine
  - Food/water depletion estimation
  - Volunteer workload analysis
  - Email alert sender
  - Overflow alert trigger
────────────────────────────────────────────────────────────────
"""

import math
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# DISTANCE UTILITY (Haversine formula)
# ─────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


# ─────────────────────────────────────────────
# 1. SHELTER RECOMMENDATION
# ─────────────────────────────────────────────

# def get_shelter_recommendations(origin_lat: float, origin_lon: float,
#                                  district: str = None, top_n: int = 3) -> list:
#     """
#     Returns top_n shelter recommendations sorted by composite score.
#     Score considers: distance, occupancy load, accessibility, medical availability.
#     """
#     from .models import Shelter

#     qs = Shelter.objects.filter(status="active")
#     if district:
#         qs = qs.filter(district=district)

#     scored = []
#     for s in qs:
#         occ_pct = s.occupancy_pct

#         # Skip completely full shelters
#         if occ_pct >= 98:
#             continue

#         dist_km    = haversine_km(origin_lat, origin_lon, s.latitude, s.longitude)
#         free_slots = s.max_capacity - s.current_occupancy

#         # ── Score (lower is better for distance, higher is better overall) ──
#         # Normalise distance: 0km=1.0, 50km=0.0
#         dist_score  = max(0, 1 - dist_km / 50)
#         # Availability score: free slots relative to capacity
#         avail_score = 1 - (occ_pct / 100)
#         # Bonus for accessible / medical
#         bonus       = (0.1 if s.is_accessible else 0) + (0.1 if s.has_medical else 0)

#         composite = (dist_score * 0.45) + (avail_score * 0.45) + bonus

#         scored.append({
#             "shelter":        s,
#             "distance_km":    round(dist_km, 1),
#             "free_slots":     free_slots,
#             "occupancy_pct":  occ_pct,
#             "composite":      round(composite, 3),
#             "accessible":     s.is_accessible,
#             "has_medical":    s.has_medical,
#         })

#     scored.sort(key=lambda x: x["composite"], reverse=True)
#     return scored[:top_n]


# ─────────────────────────────────────────────
# OSRM ROAD DISTANCE (OpenStreetMap Routing)
# ─────────────────────────────────────────────

def osrm_road_distance(origin_lat, origin_lon, dest_lat, dest_lon):
    """
    Returns (distance_km, duration_min) via OSRM public API.
    Falls back to Haversine if API fails.
    """
    import urllib.request
    import json as _json

    try:
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
            f"?overview=false&timeout=5"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "DeltaOps/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
        if data.get("code") == "Ok":
            route = data["routes"][0]
            dist_km  = round(route["distance"] / 1000, 1)
            dur_min  = round(route["duration"] / 60, 0)
            return dist_km, int(dur_min)
    except Exception as e:
        print(f"  [OSRM] ⚠️  API failed ({e}) — falling back to Haversine")

    # Fallback: straight-line with ~1.3x road factor
    straight = haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
    return round(straight * 1.3, 1), None


# ─────────────────────────────────────────────
# 1. SHELTER RECOMMENDATION
# ─────────────────────────────────────────────

def get_shelter_recommendations(origin_lat: float, origin_lon: float,
                                 district: str = None, top_n: int = 3) -> list:
    """
    Returns top_n shelter recommendations sorted by composite score.
    Uses OSRM for real road distances. Falls back to Haversine if unavailable.
    Score considers: road distance, occupancy load, accessibility, medical availability.
    """
    from .models import Shelter

    qs = Shelter.objects.filter(status="active")
    if district:
        qs = qs.filter(district=district)

    # ── Step 1: Quick Haversine pre-filter (avoid OSRM calls for far shelters) ──
    candidates = []
    for s in qs:
        occ_pct = s.occupancy_pct
        if occ_pct >= 98:
            continue
        straight_km = haversine_km(origin_lat, origin_lon, s.latitude, s.longitude)
        candidates.append((straight_km, s))

    # Sort by straight-line distance, take top 10 for OSRM lookup
    candidates.sort(key=lambda x: x[0])
    candidates = candidates[:10]

    print(f"  [RECOMMEND] {len(candidates)} candidates shortlisted for OSRM road distance lookup")

    # ── Step 2: Get real road distances via OSRM ──
    scored = []
    for straight_km, s in candidates:
        occ_pct    = s.occupancy_pct
        free_slots = s.max_capacity - s.current_occupancy

        road_km, duration_min = osrm_road_distance(
            origin_lat, origin_lon, s.latitude, s.longitude
        )

        print(f"  [OSRM] {s.name}: straight={straight_km}km → road={road_km}km"
              f"{f' ({duration_min} min)' if duration_min else ' (est.)'}")

        # ── Composite score ──
        # Normalise road distance: 0km=1.0, 80km=0.0  (wider range than before)
        dist_score  = max(0, 1 - road_km / 80)
        avail_score = 1 - (occ_pct / 100)
        bonus       = (0.1 if s.is_accessible else 0) + (0.1 if s.has_medical else 0)
        composite   = (dist_score * 0.45) + (avail_score * 0.45) + bonus

        scored.append({
            "shelter":        s,
            "distance_km":    road_km,
            "duration_min":   duration_min,   # ← new field
            "free_slots":     free_slots,
            "occupancy_pct":  occ_pct,
            "composite":      round(composite, 3),
            "accessible":     s.is_accessible,
            "has_medical":    s.has_medical,
        })

    scored.sort(key=lambda x: x["composite"], reverse=True)
    return scored[:top_n]


# ─────────────────────────────────────────────
# 2. FOOD & WATER DEPLETION ESTIMATION
# ─────────────────────────────────────────────

# Default per-person-per-day consumption benchmarks
DEFAULT_FOOD_KG_PER_PERSON  = 0.75   # ~750g food/day
DEFAULT_WATER_L_PER_PERSON  = 3.0    # 3 litres/day

def get_supply_estimates(shelter) -> dict:
    """
    Returns food/water status by merging two sources:
      1. SupplyLog (physical stock — gives days remaining estimate)
      2. ShelterStatusUpdate.food_status/water_status (volunteer/manager report — gives ground truth)
    The WORSE of the two statuses wins. If volunteer says OUT, we show OUT even if stock log says ok.
    """
    from .models import SupplyLog

    # Status severity ranking (higher = worse)
    SEVERITY = {"ok": 0, "low": 1, "out_soon": 2, "critical": 3, "out": 4, "no_data": -1, "unknown": -1}

    result = {"food": None, "water": None}

    # ── Get latest volunteer/manager reported status ──
    latest_update = shelter.latest_status  # ShelterStatusUpdate or None
    reported = {
        "food":  getattr(latest_update, "food_status",  "ok") if latest_update else None,
        "water": getattr(latest_update, "water_status", "ok") if latest_update else None,
    }

    for supply_type in ("food", "water"):
        log = (SupplyLog.objects
               .filter(shelter=shelter, supply_type=supply_type)
               .order_by("-logged_at")
               .first())

        # ── Compute days remaining from stock log ──
        days = None
        stock_status = None

        if log:
            occupancy = shelter.current_occupancy or 1
            rate = log.consumption_rate
            if rate == 0:
                rate = DEFAULT_FOOD_KG_PER_PERSON if supply_type == "food" else DEFAULT_WATER_L_PER_PERSON
            daily_usage = rate * occupancy
            days = round(log.quantity_available / daily_usage, 1) if daily_usage > 0 else None

            if days is None:   stock_status = "unknown"
            elif days <= 0.5:  stock_status = "critical"
            elif days <= 1:    stock_status = "out_soon"
            elif days <= 3:    stock_status = "low"
            else:              stock_status = "ok"
        else:
            stock_status = "no_data"
            daily_usage  = 0

        # ── Merge: take the WORSE status ──
        reported_status = reported.get(supply_type)
        if reported_status and reported_status in SEVERITY:
            final_status = (
                reported_status
                if SEVERITY.get(reported_status, -1) >= SEVERITY.get(stock_status, -1)
                else stock_status
            )
        else:
            final_status = stock_status if stock_status else "no_data"

        result[supply_type] = {
            "quantity_available": log.quantity_available if log else None,
            "consumption_rate":   log.consumption_rate if log else None,
            "daily_usage":        round(daily_usage, 2) if log else None,
            "days_remaining":     days,
            "status":             final_status,
            "reported_status":    reported_status,   # raw volunteer report
            "stock_status":       stock_status,       # from supply log
            "logged_at":          log.logged_at if log else None,
        }

    return result


# ─────────────────────────────────────────────
# 3. VOLUNTEER WORKLOAD ANALYSIS
# ─────────────────────────────────────────────

# Recommended ratio: 1 volunteer per N occupants
RECOMMENDED_VOL_PER_OCCUPANTS = 10

def get_volunteer_workload(shelter) -> dict:
    """
    Analyses volunteer distribution and workload for a shelter.
    Returns staffing status and reallocation suggestions.
    """
    from .models import Volunteer

    all_vols    = shelter.volunteers.filter(status="active")
    total_vols  = all_vols.count()
    occupancy   = shelter.current_occupancy or 1

    needed      = max(1, occupancy // RECOMMENDED_VOL_PER_OCCUPANTS)
    surplus     = total_vols - needed

    # Task breakdown
    task_counts = {}
    for v in all_vols:
        task_counts[v.task] = task_counts.get(v.task, 0) + 1

    # Identify gaps (0 volunteers for critical tasks)
    critical_tasks = ["cooking", "registration", "medical"]
    gaps = [t for t in critical_tasks if task_counts.get(t, 0) == 0]

    if surplus < -3:
        status = "critically_understaffed"
    elif surplus < 0:
        status = "understaffed"
    elif surplus > 5:
        status = "overstaffed"
    else:
        status = "adequate"

    return {
        "total_active_volunteers": total_vols,
        "volunteers_needed":       needed,
        "surplus":                 surplus,
        "status":                  status,
        "task_breakdown":          task_counts,
        "critical_task_gaps":      gaps,
    }


# ─────────────────────────────────────────────
# 4. EMAIL ALERT SENDER
# ─────────────────────────────────────────────

def send_shelter_alert_email(shelter, alert_type: str, message: str):
    """Send email alert to super admin and shelter manager."""
    recipients = []

    # Super admin emails
    try:
        from super_admin.models import super_admin as SuperAdmin
        admins = SuperAdmin.objects.filter(is_active=1)
        recipients += [a.email for a in admins if a.email]
    except Exception:
        pass

    # Shelter manager email
    if shelter.manager and shelter.manager.email:
        recipients.append(shelter.manager.email)

    if not recipients:
        print(f"[ALERT EMAIL] ⚠️  No recipients configured — skipping email for '{alert_type}'")
        logger.warning("No recipients for shelter alert email.")
        return

    subject_map = {
        "overflow_high": f"🚨 HIGH Overflow Risk — {shelter.name}",
        "food_low":      f"⚠️ Food Supply Low — {shelter.name}",
        "water_low":     f"⚠️ Water Supply Low — {shelter.name}",
        "understaffed":  f"⚠️ Understaffed Shelter — {shelter.name}",
    }

    subject = subject_map.get(alert_type, f"Shelter Alert — {shelter.name}")
    body    = f"""Kerala Flood Shelter Alert System
{'='*50}

Shelter  : {shelter.name}
District : {shelter.district}
Alert    : {alert_type.upper()}

{message}

Current Occupancy : {shelter.current_occupancy} / {shelter.max_capacity}
Occupancy %       : {shelter.occupancy_pct}%

Please take immediate action.

— Kerala Flood Prediction System
"""

    print(f"[ALERT EMAIL] Sending '{alert_type}' alert for '{shelter.name}' → {recipients}")
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
        print(f"[ALERT EMAIL] ✅ Alert email sent successfully to {recipients}")
        return True
    except Exception as e:
        logger.error("Failed to send shelter alert email: %s", e)
        print(f"[ALERT EMAIL] ❌ Failed to send alert email: {e}")
        return False


# ─────────────────────────────────────────────
# 5. MASTER ALERT TRIGGER (call after each update)
# ─────────────────────────────────────────────

def trigger_shelter_alerts(shelter, ml_result: dict = None, supply_data: dict = None,
                            workload_data: dict = None):
    """
    Checks all alert conditions for a shelter and creates ShelterAlert records.
    Sends email for new unresolved alerts (deduplication: no repeat email within 6h).
    """
    from .models import ShelterAlert

    print(f"  [ALERT CHECK] ── '{shelter.name}' ──────────────────────────────")

    def _should_send(alert_type):
        """Return True if no unresolved alert of this type was sent in last 6 hours."""
        cutoff = timezone.now() - timedelta(hours=6)
        recent = ShelterAlert.objects.filter(
            shelter=shelter, alert_type=alert_type,
            is_resolved=False, created_at__gte=cutoff
        ).exists()
        if recent:
            print(f"  [ALERT CHECK] ⏭  '{alert_type}' already triggered within 6h — skipping email")
        return not recent

    def _create_alert(alert_type, message):
        # Keep only ONE unresolved alert per type per shelter.
        # If duplicates already exist (from old bug), delete the extras and keep latest.
        existing_qs = ShelterAlert.objects.filter(
            shelter=shelter, alert_type=alert_type, is_resolved=False
        ).order_by("-created_at")

        count = existing_qs.count()
        if count > 1:
            # Delete all but the newest one
            ids_to_delete = list(existing_qs.values_list("id", flat=True)[1:])
            ShelterAlert.objects.filter(id__in=ids_to_delete).delete()
            print(f"  [ALERT CLEANUP] 🧹 Removed {count - 1} duplicate '{alert_type}' alerts")

        existing = existing_qs.first()
        if existing:
            # Update message in place so it stays fresh
            existing.message = message
            existing.save(update_fields=["message"])
            print(f"  [ALERT CHECK] ⏭  '{alert_type}' already open (ID:{existing.id}) — updated message")
            return

        alert = ShelterAlert.objects.create(
            shelter=shelter, alert_type=alert_type, message=message,
        )
        print(f"  [ALERT CREATED] 🆕 Type: {alert_type} | ID:{alert.id} | '{shelter.name}'")

        # Send email only if no email was sent in last 6h
        if _should_send(alert_type):
            sent = send_shelter_alert_email(shelter, alert_type, message)
            alert.email_sent = sent
            alert.save()
        else:
            print(f"  [ALERT EMAIL] Skipped (6h cooldown) for '{alert_type}'")

    # ── 1. Overflow Risk HIGH ──
    if ml_result and ml_result.get("risk") == "high":
        print(f"  [ALERT CHECK] 🚨 HIGH overflow risk detected ({ml_result['probability']:.0%})")
        msg = (f"ML model predicts HIGH overflow risk "
               f"({ml_result['probability']:.0%} probability) within 6–12 hours.")
        _create_alert("overflow_high", msg)
    else:
        risk = ml_result.get("risk", "unknown") if ml_result else "no ml data"
        print(f"  [ALERT CHECK] ✅ Overflow risk: {risk} — no alert needed")

    # ── 2. Food / Water Low ──
    if supply_data:
        for supply_type in ("food", "water"):
            info   = supply_data.get(supply_type, {})
            status = info.get("status", "no_data")
            days   = info.get("days_remaining")
            if status in ("critical", "out_soon", "low", "out"):
                print(f"  [ALERT CHECK] ⚠️  {supply_type.upper()} is '{status}' — {days}d remaining")
                msg = (f"{supply_type.capitalize()} supply at {shelter.name} "
                       f"estimated to last {days} days." if days else
                       f"{supply_type.capitalize()} supply critically low.")
                _create_alert(f"{supply_type}_low", msg)
            else:
                print(f"  [ALERT CHECK] ✅ {supply_type.upper()} status: {status} — no alert needed")
    else:
        print(f"  [ALERT CHECK] No supply data provided — skipping food/water check")

    # ── 3. Understaffed ──
    if workload_data and workload_data.get("status") in ("understaffed", "critically_understaffed"):
        surplus = workload_data["surplus"]
        gaps    = workload_data.get("critical_task_gaps", [])
        print(f"  [ALERT CHECK] ⚠️  UNDERSTAFFED — short by {abs(surplus)} volunteer(s) | Gaps: {gaps or 'none'}")
        msg = (f"Shelter is short by {abs(surplus)} volunteer(s). "
               f"Critical gaps: {', '.join(gaps) or 'none detected'}.")
        _create_alert("understaffed", msg)
    else:
        wl_status = workload_data.get("status", "no data") if workload_data else "no workload data"
        print(f"  [ALERT CHECK] ✅ Staffing status: {wl_status} — no alert needed")

    print(f"  [ALERT CHECK] ── Done for '{shelter.name}' ─────────────────────")
