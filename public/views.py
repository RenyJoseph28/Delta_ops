# In public/views.py
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import public_users
import re
from django.utils import timezone
from datetime import timedelta
import uuid
from .helpers import send_otp_email, generate_otp
from django.core.cache import cache
from utils.weather import get_weather_for_district
import json



# Home view
def home(request):
    return render(request,'public/index.html')


# Signin view to handle user login
def signin(request):
    if request.method == 'POST':
        # Get form data
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        
        # Validate input
        if not email or not password:
            messages.error(request, 'Please enter both email and password.')
            return render(request, 'public/signin.html', {'email': email})
        
        try:
            # Get user by email
            user = public_users.objects.get(email=email)
            
            # Check if account is active
            if not user.is_active:
                messages.error(request, 'Your account has been deactivated. Please contact support.')
                return render(request, 'public/signin.html', {'email': email})
            
            # Verify password
            if check_password(password, user.password):

                # Check if email is verified
                if user.email_verified is None:
                    # Generate OTP
                    otp = generate_otp()
                    
                    # Store OTP in session with timestamp
                    request.session['otp'] = otp
                    request.session['otp_email'] = email
                    request.session['otp_generated_at'] = timezone.now().isoformat()
                    request.session['user_id_pending'] = user.id
                    
                    # Send OTP email
                    if send_otp_email(email, otp):
                        messages.success(request, 'OTP has been sent to your email.')
                        return redirect('verify_otp')
                    else:
                        messages.error(request, 'Failed to send OTP. Please try again.')
                        return render(request, 'public/signin.html', {'email': email})
                    
                else:
                    
                    # Password is correct - create session
                    request.session['user_id'] = user.id
                    request.session['user_email'] = user.email
                    request.session['user_name'] = user.fullname
                    request.session['user_district'] = user.district
                    
                    messages.success(request, f'Welcome back, {user.fullname}!')
                    return redirect('dashboard')
            else:
                # Incorrect password
                messages.error(request, 'Invalid email or password.')
                return render(request, 'public/signin.html', {'email': email})
                
        except public_users.DoesNotExist:
            # User not found
            messages.error(request, 'Invalid email or password.')
            return render(request, 'public/signin.html', {'email': email})
        
        except Exception as e:
            # Handle any other errors
            messages.error(request, 'An error occurred. Please try again.')
            return render(request, 'public/signin.html', {'email': email})
    
    # GET request - show signin form
    return render(request, 'public/signin.html')


# OTP Verification view
def verify_otp(request):
    # Check if OTP session exists
    if 'otp' not in request.session:
        messages.error(request, 'No OTP request found. Please sign in again.')
        return redirect('signin')
    
    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        
        # Get OTP details from session
        stored_otp = request.session.get('otp')
        otp_generated_at = request.session.get('otp_generated_at')
        user_id = request.session.get('user_id_pending')
        
        # Check OTP expiration (5 minutes)
        generated_time = timezone.datetime.fromisoformat(otp_generated_at)
        current_time = timezone.now()
        time_diff = (current_time - generated_time).total_seconds()
        
        if time_diff > 300:  # 5 minutes = 300 seconds
            messages.error(request, 'OTP has expired. Please sign in again.')
            # Clear session
            request.session.pop('otp', None)
            request.session.pop('otp_email', None)
            request.session.pop('otp_generated_at', None)
            request.session.pop('user_id_pending', None)
            return redirect('signin')
        
        # Verify OTP
        if entered_otp == stored_otp:
            # Update user's email_verified field
            user = public_users.objects.get(id=user_id)
            user.email_verified = timezone.now()
            user.save()
            
            # Create login session
            request.session['user_id'] = user.id
            request.session['user_email'] = user.email
            request.session['user_name'] = user.fullname
            request.session['user_district'] = user.district
            
            # Clear OTP session data
            request.session.pop('otp', None)
            request.session.pop('otp_email', None)
            request.session.pop('otp_generated_at', None)
            request.session.pop('user_id_pending', None)
            
            messages.success(request, 'Email verified successfully! Welcome to Delta Ops.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')
            return render(request, 'public/verify_otp.html')
    
    # Calculate remaining time
    otp_generated_at = request.session.get('otp_generated_at')
    generated_time = timezone.datetime.fromisoformat(otp_generated_at)
    
    context = {
        'email': request.session.get('otp_email'),
        'otp_generated_at': generated_time.isoformat(),
    }
    
    return render(request, 'public/verify_otp.html', context)


# Resend OTP view
def resend_otp(request):
    """Resend OTP to user"""
    if 'otp_email' not in request.session:
        messages.error(request, 'No OTP request found.')
        return redirect('signin')
    
    email = request.session.get('otp_email')
    
    # Generate new OTP
    otp = generate_otp()
    
    # Update session
    request.session['otp'] = otp
    request.session['otp_generated_at'] = timezone.now().isoformat()
    
    # Send OTP email
    if send_otp_email(email, otp):
        messages.success(request, 'New OTP has been sent to your email.')
    else:
        messages.error(request, 'Failed to send OTP. Please try again.')
    
    return redirect('verify_otp')


# Signup view to handle user registration
def signup(request):
    if request.method == 'POST':
        # Get form data
        fullname = request.POST.get('fullname', '').strip()
        email = request.POST.get('email', '').strip().lower()
        mobile = request.POST.get('mobile', '').strip()
        district = request.POST.get('district', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        terms = request.POST.get('terms')
        
        # Initialize error flag
        has_error = False
        
        # Validate full name
        if not fullname or len(fullname) < 2:
            messages.error(request, 'Please enter a valid full name (minimum 2 characters).')
            has_error = True
        
        # Validate email
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Please enter a valid email address.')
            has_error = True
        
        # Check if email already exists
        if public_users.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            has_error = True
        
        # Validate mobile number (Indian format: 10 digits)
        mobile_pattern = re.compile(r'^[6-9]\d{9}$')
        if not mobile_pattern.match(mobile):
            messages.error(request, 'Please enter a valid 10-digit mobile number.')
            has_error = True
        
        # Validate district
        kerala_districts = [
            "Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod",
            "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad",
            "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"
        ]
        if district not in kerala_districts:
            messages.error(request, 'Please select a valid district.')
            has_error = True
        
        # Validate password strength
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            has_error = True
        elif not re.search(r'[A-Z]', password):
            messages.error(request, 'Password must contain at least one uppercase letter.')
            has_error = True
        elif not re.search(r'[a-z]', password):
            messages.error(request, 'Password must contain at least one lowercase letter.')
            has_error = True
        elif not re.search(r'\d', password):
            messages.error(request, 'Password must contain at least one number.')
            has_error = True
        
        # Check if passwords match
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            has_error = True
        
        # Validate terms acceptance
        if not terms:
            messages.error(request, 'You must agree to the Terms of Service and Privacy Policy.')
            has_error = True
        
        # If there are errors, return to signup page with form data
        if has_error:
            context = {
                'fullname': fullname,
                'email': email,
                'mobile': mobile,
                'district': district,
            }
            return render(request, 'public/signup.html', context)
        
        # All validations passed, create user
        try:
            # Hash the password
            hashed_password = make_password(password)
            
            # Create new user
            user = public_users.objects.create(
                fullname=fullname,
                email=email,
                mobile=mobile,
                district=district,
                password=hashed_password
            )
            
            # Success message
            messages.success(request, 'Account created successfully! Please sign in.')
            return redirect('signin')
            
        except Exception as e:
            messages.error(request, f'An error occurred while creating your account. Please try again.')
            return render(request, 'public/signup.html')
    
    # GET request - show signup form
    return render(request, 'public/signup.html')

# Logout view to handle user signout
def signout(request):
    """Logout user by clearing session"""
    request.session.flush()
    messages.success(request, 'You have been successfully logged out.')
    return redirect('signin')

# Dashboard view (protected)
def dashboard(request):
    # Check if user is logged in
    if 'user_id' not in request.session:
        messages.error(request, 'Please sign in to access the dashboard.')
        return redirect('signin')
    
    try:
        user_id = request.session['user_id']
        user = public_users.objects.get(id=user_id, is_active=True)
        
        # Get weather data for user's district
        district = user.district
        
        # Create cache key
        cache_key = f"weather_{district}"
        
        # Try to get from cache first
        weather_data = cache.get(cache_key)
        
        if not weather_data:
            # Fetch fresh weather data
            weather_data = get_weather_for_district(district)
            
            if weather_data:
                # Cache for 10 minutes
                cache.set(cache_key, weather_data, 600)
        
        context = {
            'user_name': user.fullname,
            'user_email': user.email,
            'user_district': user.district,
            'weather_data': weather_data,
        }
        
        return render(request, 'public/dashboard.html', context)
        
    except public_users.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('signin')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
        return render(request, 'public/dashboard.html', {
            'user_name': request.session.get('user_name', 'User'),
            'user_email': request.session.get('user_email', ''),
            'user_district': request.session.get('user_district', ''),
            'weather_data': None,
        })
