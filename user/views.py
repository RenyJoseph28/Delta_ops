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
