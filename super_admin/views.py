from django.shortcuts import render,redirect

from django.http import HttpResponse
from .models import *
from django.utils import timezone
from django.contrib import messages

# super_admin/views.py
from django.shortcuts import render, redirect

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.contrib.auth.hashers import check_password, make_password
from .helpers import fetch_weather_for_city, send_weather_email_alert

from django.views.decorators.http import require_POST

from django.utils.timezone import now

from public.models import public_users



# --- LOGIN / LOGOUT ---
def super_admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        try:
            admin = super_admin.objects.get(username=username)
        except super_admin.DoesNotExist:
            messages.error(request, "Invalid username or password")
            return render(request, "super_admin/login.html")

        # If admin.password is hashed, use check_password; otherwise fallback to plain compare (not recommended)
        try:
            if check_password(password, admin.password):
                pass
            else:
                messages.error(request, "Invalid username or password")
                return render(request, "super_admin/login.html")
        except Exception:
            # If check_password throws (e.g., password not hashed), fallback (legacy)
            if admin.password != password:
                messages.error(request, "Invalid username or password")
                return render(request, "super_admin/login.html")

        admin.last_login = timezone.now()
        admin.save()

        request.session["super_admin_id"] = admin.id
        request.session["super_admin_username"] = admin.username

        return redirect("super_admin_dashboard")

    return render(request, "super_admin/login.html")


def super_admin_logout(request):
    request.session.flush()
    return redirect("admin_login")


# --- DASHBOARD ---
def super_admin_dashboard(request):
    if "super_admin_id" not in request.session:
        return redirect("admin_login")
    
    today = timezone.localdate()

    # quick stats
    total_users = public_users.objects.count()
    active_users = public_users.objects.filter(is_active=True, email_verified__isnull=False).count()
    recent_users = public_users.objects.order_by("-created_at")[:5]

    alerts_today = weather_alerts.objects.filter(
        sent_at__date=today
    ).count()

    print("alerts_today:", alerts_today)

    # default district for weather widget - we can show statewide or pick one; using Thiruvananthapuram as default
    default_district = request.GET.get("district") or "Thiruvananthapuram"
    weather = fetch_weather_for_city(default_district)

    context = {
        "admin_username": request.session.get("super_admin_username"),
        "total_users": total_users,
        "active_users": active_users,
        "alerts_today": alerts_today,
        "recent_users": recent_users,
        "weather_data": weather,
        "default_district": default_district,
    }
    return render(request, "super_admin/dashboard.html", context)


# --- USERS LIST ---
def signup_users_list(request):
    if "super_admin_id" not in request.session:
        return redirect("admin_login")

    q = request.GET.get("q", "").strip()
    page = request.GET.get("page", 1)
    users_qs = public_users.objects.all().order_by("-created_at")

    if q:
        users_qs = users_qs.filter(
            # simple search across name/email/mobile
            fullname__icontains=q
        ) | users_qs.filter(email__icontains=q) | users_qs.filter(mobile__icontains=q)

    paginator = Paginator(users_qs, 15)  # 15 users per page
    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)

    context = {
        "users_page": users_page,
        "q": q,
    }
    return render(request, "super_admin/users_list.html", context)


# --- AJAX weather endpoint ---
def admin_get_weather(request):
    if "super_admin_id" not in request.session:
        return JsonResponse({"error": "unauthorized"}, status=401)

    district = request.GET.get("district", "Thiruvananthapuram")
    weather = fetch_weather_for_city(district)
    if not weather:
        return JsonResponse({"error": "failed"}, status=500)
    
    # 🔥 SEND EMAIL ALERT
    send_weather_email_alert(district, weather)

    return JsonResponse(weather)




@require_POST
def send_manual_weather_alert(request):
    if "super_admin_id" not in request.session:
        return JsonResponse({"error": "unauthorized"}, status=401)

    district = request.POST.get("district")

    if not district:
        return JsonResponse({"error": "District required"}, status=400)

    weather = fetch_weather_for_city(district)

    if not weather:
        return JsonResponse({"error": "Failed to fetch weather"}, status=500)

    # 🔔 Send email alert
    send_weather_email_alert(district, weather)

    return JsonResponse({
        "success": True,
        "message": f"Alert triggered for {district}"
    })