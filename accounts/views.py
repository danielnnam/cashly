from django.dispatch import receiver
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
# from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialLogin
from allauth.socialaccount.helpers import complete_social_login
from django.contrib.auth import login
from django.contrib.auth.backends import ModelBackend
from wallet.models import Wallet, Transaction   
from django.urls import reverse
from django.db.models import Q
from django.db import models
from .forms import UserForm, ProfileForm
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth import update_session_auth_hash
from .forms import StyledPasswordChangeForm, StyledSetPasswordForm
from django.contrib.auth.signals import user_logged_in
from django.utils import timezone
from .models import LoginActivity, Notification
from django.contrib.sessions.models import Session
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.contrib.messages import get_messages, add_message, INFO
from accounts.utils import create_notification
from django.utils.timezone import now





@csrf_protect
def home(request):
    """Home page view"""
    return render(request, 'simplebank_project/home.html')

def get_client_ip(request):
    """Get real client IP address"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


@csrf_protect
def login_view(request):
    """Custom login view that works with email authentication"""
    if request.method == 'POST':
        email = request.POST.get('username')  # This is actually the email
        password = request.POST.get('password')
        remember_me = request.POST.get('remember-me')

        # Try to authenticate with email → get user’s actual username
        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            username = email  # fallback

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Session expiry
            if not remember_me:
                request.session.set_expiry(0)        # expires on browser close
            else:
                request.session.set_expiry(1209600)  # 2 weeks

            # Success message
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')

            # ✅ Track login activity
            user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")
            ip = get_client_ip(request)

            LoginActivity.objects.create(
                user=user,
                ip_address=ip,
                user_agent=user_agent,
                session_key=request.session.session_key,
                timestamp=timezone.now()
            )

            # ✅ Smart redirect logic
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)

            # 🔹 If admin/staff, go to custom admin dashboard
            if user.is_staff or user.is_superuser:
                return redirect('admin_dashboard:admin_dashboard')

            # 🔹 Else, go to user dashboard
            return redirect('dashboard')
            
        else:
            messages.error(request, 'Invalid email or password. Please try again.')

    return render(request, 'accounts/login.html')


@csrf_protect
def register_view(request):
    # Clear out any leftover messages
    storage = get_messages(request)
    for _ in storage:  # loop to consume them
        pass
    """User registration view with backend specification"""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        full_name = request.POST.get('fullname')
        terms = request.POST.get('terms')
        
        # Validation
        errors = []
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if User.objects.filter(email=email).exists():
            errors.append('Email address is already registered.')
        if not terms:
            errors.append('You must agree to the terms and conditions.')
        
        if not errors:
            try:
                # Create user
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=full_name
                )
                
                # ✅ FIX: Specify the authentication backend
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                messages.success(request, f'Account created successfully! Welcome to Cashly, {user.first_name or user.username}!')
                return redirect('dashboard')
                
            except Exception as e:
                messages.error(request, f'An error occurred during registration: {str(e)}')
        else:
            for error in errors:
                messages.error(request, error)
    
    return render(request, 'accounts/register.html')

@csrf_protect
def logout_view(request):
    """Logout view"""
    logout(request)
    messages.info(request, 'You have been successfully logged out.')
    return redirect('home')


@login_required
def dashboard(request):
    """User dashboard view"""
    try:
        wallet = Wallet.objects.get(user=request.user)  # force DB fetch
    except Wallet.DoesNotExist:
        wallet = None

    balance = wallet.balance if wallet else 0.00
    unread_count = request.user.user_notifications.filter(is_read=False).count()

    if wallet:
        recent_transactions = Transaction.objects.filter(
            models.Q(sender=wallet) | models.Q(receiver=wallet)
        ).order_by('-created_at')[:5]

        # Transactions this month
        today = now()
        month_transactions = Transaction.objects.filter(
            models.Q(sender=wallet) | models.Q(receiver=wallet),
            created_at__year=today.year,
            created_at__month=today.month
        ).count()
    else:
        recent_transactions = []
        month_transactions = 0

    context = {
        'user': request.user,
        'unread_count': unread_count,
        'wallet': wallet,
        'balance': balance,
        'recent_transactions': recent_transactions,
        'month_transactions': month_transactions,
        'balance_api_url': reverse('wallet:get_balance_api'),
    }
    return render(request, 'dashboard/dashboard.html', context)



def google_callback(request):
    """Minimal callback that lets Allauth handle the heavy lifting"""
    try:
        # Let Allauth process the login
        login = SocialLogin.deserialize(request)
        return complete_social_login(request, login)
    except Exception as e:
        messages.error(request, 'Google authentication failed.')
        return redirect('login_view')



@login_required
def settings_view(request):
    # Dummy data for now (later replace with DB models)
    context = {
        "default_payment": "Wallet Balance",
        "bank_accounts": [
            {"bank_name": "GTBank", "account_number": "0123456789", "account_name": "John Doe"},
        ],
        "saved_cards": [
            {"last4": "4321", "name": "John Doe", "expiry": "12/25"},
        ],
        "transaction_limits": {"daily": 20000, "weekly": 100000},
        "notifications": {
            "transaction_alerts": True,
            "low_balance_alerts": False,
            "large_transaction_alerts": True,
        },
    }
    return render(request, "accounts/settings.html", context)


@login_required
def edit_profile(request):
    user_form = UserForm(instance=request.user)
    profile_form = ProfileForm(instance=request.user.profile)

    if request.method == "POST":
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(
            request.POST, request.FILES, instance=request.user.profile
        )

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("settings")
        else:
            messages.error(request, "Please correct the errors below.")

    return render(
        request,
        "accounts/edit_profile.html",
        {"user_form": user_form, "profile_form": profile_form},
    )



@login_required
def change_password(request):
    if request.user.has_usable_password():
        form_class = StyledPasswordChangeForm
    else:
        form_class = StyledSetPasswordForm

    form = form_class(request.user, request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # keep user logged in
            create_notification(request.user, "Password Changed", "Your password was successfully updated.")
            return redirect("settings")  # change to your success page
    
    return render(request, "accounts/change_password.html", {"form": form})




@receiver(user_logged_in)
def track_login(sender, request, user, **kwargs):
    LoginActivity.objects.create(
        user=user,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        timestamp=timezone.now()
    )



@login_required
@csrf_protect
def logout_sessions(request):
    if request.method == "POST":
        session_key = request.POST.get("sessions")
        if session_key and session_key != request.session.session_key:
            # Delete the session itself
            Session.objects.filter(session_key=session_key).delete()
            
            # Also delete the login activity record
            LoginActivity.objects.filter(session_key=session_key, user=request.user).delete()
            
            messages.success(request, "Session deleted successfully.")
        else:
            messages.warning(request, "You cannot delete the current session.")
    return redirect("login_activity") 


def login_activity(request):
    activities = LoginActivity.objects.filter(user=request.user).order_by("-timestamp")

    # Deduplicate by (ip + user_agent)
    seen = set()
    unique_activities = []
    for act in activities:
        key = (act.ip_address, act.user_agent)
        if key not in seen:
            seen.add(key)
            unique_activities.append(act)

    return render(request, "accounts/login_activity.html", {"activities": unique_activities})



@login_required
def notifications_list(request):
    notifications = request.user.user_notifications.all()
    return render(request, "accounts/notifications_list.html", {"notifications": notifications})

@login_required
def mark_notification_as_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    return redirect("notifications_list")


@login_required
def switch_to_user(request):
    request.session['role'] = 'user'
    return redirect('dashboard')  # normal user dashboard


@login_required
def switch_to_agent(request):
    profile = request.user.profile

    # Check if the user is actually an agent
    if not profile.is_agent:
        messages.error(request, "You are not an approved agent.")
        return redirect('dashboard')

    # Check if suspended
    if profile.is_suspended:
        messages.warning(request, "Your agent account is suspended.")
        return redirect('agents:suspension_notice')

    # All good — switch role
    request.session['role'] = 'agent'
    return redirect('agents:dashboard')

def logout_view(request):
    """Simple logout view"""
    logout(request)
    return redirect('home')