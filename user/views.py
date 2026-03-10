from django.shortcuts import render, redirect

from django.utils import timezone
from super_admin.models import weather_alerts
from public.models import public_users

from django.http import HttpResponse

def profile(request):
    return HttpResponse("User Profile Page")

# --- USER ALERTS VIEW ---
def user_alerts(request):
    if "user_id" not in request.session:
        return redirect("signin")

    user = public_users.objects.get(id=request.session["user_id"])

    alerts = weather_alerts.objects.filter(
        district__iexact=user.district
    ).order_by("-sent_at")[:20]

    return render(request, "user/alerts.html", {
        "alerts": alerts,
        "user_district": user.district
    })


# --- SHELTER FINDER VIEW ---
def shelter_finder(request):
    """
    Public-facing shelter finder page.
    The page itself is static — shelter data is loaded via AJAX
    from the existing /shelters/admin/shelters/recommendations/ endpoint.
    """
    if "user_id" not in request.session:
        return redirect("signin")

    try:
        user = public_users.objects.get(
            id=request.session["user_id"],
            is_active=True
        )
    except public_users.DoesNotExist:
        return redirect("signin")

    return render(request, "user/shelter_finder.html", {
        "user_name":     user.fullname,
        "user_district": user.district,
    })





















































