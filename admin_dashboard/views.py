from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count
from django.contrib.auth.models import User
from agents.models import AgentApplication
from wallet.models import Transaction 
from decimal import Decimal
from datetime import timedelta
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from .models import ActivityLog
from django.db.models import Q
from django.contrib import messages


def is_admin_user(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_admin_user)
def admin_dashboard(request):
    """Custom Admin Dashboard with live system stats"""

    # Total users
    total_users = User.objects.count()

    # Active agents (approved ones)
    active_agents = AgentApplication.objects.filter(status='approved').count()

    # Total transactions and volume
    total_transactions = Transaction.objects.count()
    total_volume = Transaction.objects.aggregate(total=Sum('amount'))['total'] or 0

    total_fees =  0
    system_revenue = Decimal(total_fees) * Decimal('0.6')

    users = (
        User.objects.select_related("profile")
        .order_by("-date_joined")[:10]  # Show latest 10 users
    )

    context = {
        'total_users': total_users,
        'active_agents': active_agents,
        'total_transactions': total_transactions,
        'total_volume': total_volume,
        'system_revenue': system_revenue,
        "users": users,
    }

    return render(request, "admin_dashboard/dashboard.html", context)


@login_required
def transaction_chart_data(request):
    """Return last 30 days of transaction volume for Chart.js"""
    today = timezone.now().date()
    start_date = today - timedelta(days=29)

    # Prepare daily sums
    data = []
    labels = []
    for i in range(30):
        day = start_date + timedelta(days=i)
        total = (
            Transaction.objects.filter(created_at__date=day)
            .aggregate(total=Sum('amount'))['total'] or 0
        )
        data.append(float(total))
        labels.append(day.strftime("%b %d"))  # e.g., "Oct 15"

    return JsonResponse({"labels": labels, "data": data})

@staff_member_required
@login_required
def recent_activity(request):
    if request.user.is_staff:
        activities = ActivityLog.objects.select_related("user").order_by("-created_at")[:10]
    else:
        activities = ActivityLog.objects.filter(user=request.user).select_related("user").order_by("-created_at")[:10]

    data = [
        {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "type": a.type,
            "status": a.status,
            "icon": a.icon,
            "user": a.user.username if a.user else "System",
            "time_ago": a.time_ago,
        }
        for a in activities
    ]
    return JsonResponse({"activities": data})





@login_required
@user_passes_test(is_admin_user)
def users_list(request):
    """
    Display all users in the admin dashboard with profile info.
    """
    users = User.objects.select_related('profile').all().order_by('-date_joined')
    
    context = {
        'users': users
    }
    return render(request, 'admin_dashboard/users.html', context)


@login_required
@user_passes_test(is_admin_user)
def user_detail(request, user_id):
    # Get the user and profile
    user_obj = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    profile = getattr(user_obj, "profile", None)

    # Get the user's wallet (must exist because of your post_save signal)
    wallet = getattr(user_obj, 'wallet', None)
    if wallet:
        wallet.total_deposits = wallet.received_transactions.filter(transaction_type='deposit', status='completed').aggregate(total=Sum('amount'))['total'] or 0
        wallet.total_withdrawals = wallet.sent_transactions.filter(transaction_type='withdrawal', status='completed').aggregate(total=Sum('amount'))['total'] or 0


    # Fetch transactions for this wallet (both sent and received)
    transactions = wallet.get_transaction_history() if wallet else []

    # Recent activity logs
    activities = ActivityLog.objects.filter(user=user_obj).order_by("-created_at")[:10]

    context = {
        "user_obj": user_obj,
        "profile": profile,
        "wallet": wallet,
        "transactions": transactions[:10],  # show only last 10
        "activities": activities,
    }
    return render(request, "admin_dashboard/user_detail.html", context)

@login_required
@user_passes_test(is_admin_user)
def suspend_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    # Prevent admin from suspending themselves
    if request.user == user:
        messages.error(request, "You cannot suspend your own account.")
        return redirect('admin_dashboard:user_detail', user_id=user.id)

    # Toggle active status
    user.is_active = not user.is_active
    user.save()

    if user.is_active:
        messages.success(request, f"{user.username} has been activated.")
    else:
        messages.success(request, f"{user.username} has been suspended.")

    return redirect('admin_dashboard:user_detail', user_id=user.id)


@login_required
@user_passes_test(is_admin_user)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    messages.success(request, f"User {user.username} has been deleted.")
    return redirect('admin_dashboard:users')
