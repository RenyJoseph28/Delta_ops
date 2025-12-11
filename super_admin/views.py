from django.shortcuts import render,redirect

from django.http import HttpResponse
from .models import *
from django.utils import timezone
from django.contrib import messages

def dashboard(request):
    return HttpResponse("Admin Dashboard Page")


def super_admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username").strip()
        password = request.POST.get("password").strip()


        # Check if user exists
        try:
            admin = super_admin.objects.get(username=username, password=password)
            print('username',username)
            print('username',password)
        except super_admin.DoesNotExist:
            print('username',username)
            print('password',password)

            messages.error(request, "Invalid username or password")
            return render(request, "super_admin/login.html")

        # Update last login time
        admin.last_login = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        print("login successfully")
        admin.save()

        # Set session
        request.session["super_admin_id"] = admin.id
        request.session["super_admin_username"] = admin.username

        return redirect("super_admin_dashboard")

    return render(request, "super_admin/login.html")



def super_admin_logout(request):
    request.session.flush()
    return redirect("super_admin_login")



def super_admin_dashboard(request):
    if "super_admin_id" not in request.session:
        return redirect("super_admin_login")

    return render(request, 'super_admin/dashboard.html')
