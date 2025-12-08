# In public/views.py
from django.shortcuts import render
from django.http import HttpResponse


def home(request):

    return render(request,'public/index.html')

def signin(request):
    return render(request, 'public/signin.html')

def signup(request):
    return render(request, 'public/signup.html')