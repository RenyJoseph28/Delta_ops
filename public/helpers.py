from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
import re
from .models import public_users

# Utility function to generate OTP
def generate_otp():
    """Generate a 6-digit OTP using UUID"""
    return str(uuid.uuid4().int)[:6]


# Utility function to send OTP email
def send_otp_email(email, otp):
    """Send OTP via email"""
    subject = 'Delta Ops - Email Verification OTP'
    message = f"""
    Hello,

    Your OTP for email verification is: {otp}

    This OTP is valid for 5 minutes only.

    If you didn't request this, please ignore this email.

    Best regards,
    Delta Ops Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False