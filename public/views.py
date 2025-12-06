# In public/views.py
from django.shortcuts import render
from django.http import HttpResponse


def home(request):
    print("HOME VIEW WAS CALLED!")

    return HttpResponse("Public Home Page")