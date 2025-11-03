from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count
from django.contrib.auth.models import User
from admin_dashboard.forms import AdminSettingsForm
from admin_dashboard.utils import log_activity
from agents.models import AgentApplication
from payments.models import DepositRequest, WithdrawalRequest
from wallet.models import Transaction 
from decimal import Decimal
from datetime import timedelta
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from .models import ActivityLog, SystemSettings
from django.db.models import Q
from django.contrib import messages
from wallet.models import Wallet
from accounts.models import Profile, Notification
from .models import AdminNotification
from django.db.models import Value, CharField
from wallet.models import Dispute, DisputeMessage
from django.utils.timezone import now
from datetime import timedelta


def is_admin_user(user):
    return user.is_staff or user.is_superuser


def create_admin_notification(title, message):
    """Send notification to all admin users."""
    admins = User.objects.filter(is_staff=True)
    for admin in admins:
        Notification.objects.create(user=admin, title=title, message=message)


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

@login_required
def log_admin_activity(user, title, description, type="info", status="success", icon="fas fa-info-circle"):
    """Log activity and send admin notification."""
    # Create activity log
    activity = ActivityLog.objects.create(
        user=user,
        title=title,
        description=description,
        type=type,
        status=status,
        icon=icon,
    )

    # Send notifications to all staff/admins
    admins = User.objects.filter(is_staff=True)
    for admin in admins:
        Notification.objects.create(
            user=admin,
            title=f"Admin Activity: {title}",
            message=description,
        )
    return activity


@staff_member_required
@login_required
def recent_activity(request):
    """Return JSON of recent activities."""
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


# 🟢 SUSPEND USER
@login_required
@user_passes_test(is_admin_user)
def suspend_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.user == user:
        messages.error(request, "You cannot suspend your own account.")
        return redirect('admin_dashboard:user_detail', user_id=user.id)

    user.is_active = not user.is_active
    user.save()

    if user.is_active:
        messages.success(request, f"{user.username} has been activated.")

        # Log activity
        log_activity(
            user=request.user,
            title="User Reinstated",
            description=f"Admin {request.user.username} reinstated user {user.username}.",
            type="user",
            status="success",
            icon="user-check"
        )

        create_admin_notification(
            "User Reinstated",
            f"{user.username}'s account has been reactivated."
        )
    else:
        messages.warning(request, f"{user.username} has been suspended.")

        # Log activity
        log_activity(
            user=request.user,
            title="User Suspended",
            description=f"Admin {request.user.username} suspended user {user.username}.",
            type="user",
            status="warning",
            icon="user-slash"
        )

        create_admin_notification(
            "User Suspended",
            f"Admin suspended user {user.username}."
        )

    return redirect('admin_dashboard:user_detail', user_id=user.id)


# 🟢 DELETE USER
@login_required
@user_passes_test(is_admin_user)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    username = user.username
    user.delete()

    messages.success(request, f"User {username} has been deleted.")

    # Log activity
    log_activity(
        user=request.user,
        title="User Deleted",
        description=f"Admin {request.user.username} deleted user {username}.",
        type="user",
        status="danger",
        icon="user-times"
    )

    create_admin_notification(
        "User Deleted",
        f"Admin deleted user account: {username}."
    )

    return redirect('admin_dashboard:users')


# 🟢 ADMIN AGENT DETAIL
@login_required
@user_passes_test(is_admin_user)
def admin_agent_detail(request, reference):
    agent_app = get_object_or_404(AgentApplication, reference=reference)
    user_obj = agent_app.user
    profile = Profile.objects.filter(user=user_obj).first()
    wallet = Wallet.objects.filter(user=user_obj).first()

    context = {
        "agent_app": agent_app,
        "user_obj": user_obj,
        "profile": profile,
        "wallet": wallet,
    }
    return render(request, "admin_dashboard/agent_detail.html", context)


# 🟢 ADMIN AGENTS LIST
@login_required
@user_passes_test(is_admin_user)
def admin_agents_list(request):
    agents = AgentApplication.objects.select_related('user').order_by('-created_at')
    status_filter = request.GET.get('status')
    if status_filter in ['pending', 'approved', 'rejected']:
        agents = agents.filter(status=status_filter)

    context = {
        'agents': agents,
        'status_filter': status_filter,
    }
    return render(request, 'admin_dashboard/agents.html', context)


# 🟢 APPROVE AGENT
@login_required
@user_passes_test(is_admin_user)
def approve_agent(request, reference):
    agent = get_object_or_404(AgentApplication, reference=reference)
    agent.status = 'approved'
    agent.save()

    messages.success(request, "Agent approved successfully.")

    # Log activity
    log_activity(
        user=request.user,
        title="Agent Approved",
        description=f"Admin {request.user.username} approved agent {agent.user.username}.",
        type="agent",
        status="success",
        icon="user-check"
    )

    create_admin_notification(
        "Agent Approved",
        f"Agent {agent.user.username} has been approved successfully."
    )
    return redirect('admin_dashboard:admin_agent_detail', reference=reference)


# 🟠 DECLINE AGENT
@login_required
@user_passes_test(is_admin_user)
def decline_agent(request, reference):
    agent_app = get_object_or_404(AgentApplication, reference=reference)
    profile = Profile.objects.get(user=agent_app.user)

    if request.method == 'POST':
        reason = request.POST.get('reason')
        agent_app.status = 'rejected'
        agent_app.decline_reason = reason
        agent_app.save()

        profile.is_agent = False
        profile.save()

        messages.error(request, f"Agent application declined. Reason: {reason}")

        # Log activity
        log_activity(
            user=request.user,
            title="Agent Declined",
            description=f"Admin {request.user.username} declined agent {agent_app.user.username}. Reason: {reason}",
            type="agent",
            status="warning",
            icon="user-slash"
        )

        create_admin_notification(
            "Agent Declined",
            f"Agent {agent_app.user.username}'s application was declined. Reason: {reason}"
        )

    return redirect('admin_dashboard:admin_agent_detail', reference=reference)


@login_required
@user_passes_test(is_admin_user)
def suspend_agent(request, reference):
    agent_app = get_object_or_404(AgentApplication, reference=reference)
    profile = get_object_or_404(Profile, user=agent_app.user)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "Please provide a reason for suspension.")
            return redirect('admin_dashboard:admin_agent_detail', reference=reference)

        profile.is_suspended = True
        profile.suspension_reason = reason
        profile.appeal_status = "none"
        profile.suspension_appeal = ""
        profile.save()

        log_activity(
            user=request.user,
            title="Agent Suspended",
            description=f"Agent {profile.user.username} has been suspended. Reason: {reason}",
            type="agent",
            status="warning",
            icon="user-slash"
        )


        messages.warning(request, f"Agent {agent_app.user.username} has been suspended. Reason: {reason}")
        create_admin_notification(
            "Agent Suspended",
            f"Agent {agent_app.user.username} has been suspended. Reason: {reason}"
        )
        return redirect('admin_dashboard:admin_agent_detail', reference=reference)

    messages.error(request, "Invalid request method.")
    return redirect('admin_dashboard:admin_agent_detail', reference=reference)


# 🟢 UNSUSPEND AGENT
@login_required
@user_passes_test(is_admin_user)
def unsuspend_agent(request, reference):
    agent_app = get_object_or_404(AgentApplication, reference=reference)
    profile = get_object_or_404(Profile, user=agent_app.user)

    if request.method == "POST":
        profile.is_suspended = False
        profile.suspension_reason = ""
        profile.suspension_appeal = ""
        profile.appeal_status = "resolved"
        profile.save()

        messages.success(request, f"Agent {agent_app.user.username} has been reinstated.")

        # Log activity
        log_activity(
            user=request.user,
            title="Agent Reinstated",
            description=f"Admin {request.user.username} reinstated agent {agent_app.user.username}.",
            type="agent",
            status="success",
            icon="user-check",
        )

        # Notify admins
        create_admin_notification(
            "Agent Reinstated",
            f"Agent {agent_app.user.username} has been reinstated successfully."
        )

        return redirect('admin_dashboard:admin_agent_detail', reference=reference)

    messages.error(request, "Invalid request method.")
    return redirect('admin_dashboard:admin_agent_detail', reference=reference)


# 🟢 ACCEPT APPEAL
@login_required
@user_passes_test(is_admin_user)
def accept_appeal(request, reference):
    agent_app = get_object_or_404(AgentApplication, reference=reference)
    profile = get_object_or_404(Profile, user=agent_app.user)

    profile.is_suspended = False
    profile.appeal_status = "reviewed"
    profile.suspension_reason = ""
    profile.suspension_appeal = ""
    profile.suspended_at = None
    profile.save()

    messages.success(request, f"Appeal accepted — {agent_app.user.username} has been reinstated as an agent.")

    # Log activity
    log_activity(
        user=request.user,
        title="Appeal Accepted",
        description=f"Admin {request.user.username} accepted appeal for agent {agent_app.user.username}.",
        type="agent",
        status="success",
        icon="thumbs-up",
    )

    # Notify admins
    create_admin_notification(
        "Appeal Accepted",
        f"Suspension appeal for {agent_app.user.username} has been accepted and reinstated."
    )

    return redirect("admin_dashboard:admin_agent_detail", reference=reference)


# 🟠 REJECT APPEAL
@login_required
@user_passes_test(is_admin_user)
def reject_appeal(request, reference):
    agent_app = get_object_or_404(AgentApplication, reference=reference)
    profile = get_object_or_404(Profile, user=agent_app.user)

    profile.appeal_status = "reviewed"
    profile.save()

    messages.warning(request, f"Appeal from {agent_app.user.username} has been rejected.")

    # Log activity
    log_activity(
        user=request.user,
        title="Appeal Rejected",
        description=f"Admin {request.user.username} rejected appeal from agent {agent_app.user.username}.",
        type="agent",
        status="warning",
        icon="ban",
    )

    # Notify admins
    create_admin_notification(
        "Appeal Rejected",
        f"Suspension appeal from {agent_app.user.username} has been rejected."
    )

    return redirect("admin_dashboard:admin_agent_detail", reference=reference)


# 🔴 DELETE AGENT
@login_required
@user_passes_test(is_admin_user)
def delete_agent(request, reference):
    agent_app = get_object_or_404(AgentApplication, reference=reference)
    profile = get_object_or_404(Profile, user=agent_app.user)

    if request.method == "POST":
        profile.is_agent = False
        profile.save()
        username = agent_app.user.username
        agent_app.delete()

        messages.error(request, f"Agent {username} has been permanently removed.")

        # Log activity
        log_activity(
            user=request.user,
            title="Agent Deleted",
            description=f"Admin {request.user.username} deleted agent {username} from the system.",
            type="agent",
            status="danger",
            icon="user-times",
        )

        # Notify admins
        create_admin_notification(
            "Agent Deleted",
            f"Agent {username} has been permanently removed from the platform."
        )

        return redirect("admin_dashboard:agents")

    messages.error(request, "Invalid request method.")
    return redirect("admin_dashboard:admin_agent_detail", reference=reference)


@login_required
@user_passes_test(is_admin_user)
def admin_notifications_page(request):
    notifications = request.user.admin_notifications.all()
    return render(request, "admin_dashboard/notifications.html", {"notifications": notifications})


@login_required
@user_passes_test(is_admin_user)
def mark_admin_notification_as_read(request, notif_id):
    notif = get_object_or_404(AdminNotification, id=notif_id, admin_user=request.user)
    notif.is_read = True
    notif.save()
    return redirect('admin_dashboard:admin_notifications')


# Transcations
@login_required
@user_passes_test(is_admin_user)
def transactions_list(request):
    """Admin transaction list view showing deposit & withdrawal records with proper TX IDs"""
    if not request.user.is_staff:
        return redirect("dashboard:home")  # only admins can view

    type_filter = request.GET.get("type")
    status_filter = request.GET.get("status")

    # ✅ remove 'transaction' from select_related
    deposits = (
        DepositRequest.objects.select_related("user", "agent")
        .order_by("-created_at")
    )
    withdrawals = (
        WithdrawalRequest.objects.select_related("user", "agent")
        .order_by("-created_at")
    )

    # Combine both into a single list
    transactions = list(deposits) + list(withdrawals)

    # Apply filters
    if type_filter:
        transactions = [tx for tx in transactions if tx.tx_type.lower() == type_filter.lower()]
    if status_filter:
        transactions = [tx for tx in transactions if tx.status.lower() == status_filter.lower()]

    # ✅ Handle display ID properly
    for tx in transactions:
        if hasattr(tx, "transaction") and tx.transaction:
            tx.display_id = tx.transaction.transaction_id
        else:
            tx.display_id = f"TEMP-{tx.id}"


    context = {
        "transactions": sorted(transactions, key=lambda t: t.created_at, reverse=True),
        "filter_type": type_filter,
        "filter_status": status_filter,
        "deposit_count": deposits.count(),
        "withdrawal_count": withdrawals.count(),
        "pending_count": deposits.filter(status="pending").count() + withdrawals.filter(status="pending").count(),
    }

    return render(request, "admin_dashboard/transactions.html", context)


# Disputes
@login_required
@user_passes_test(is_admin_user)
def disputes_list(request):
    status_filter = request.GET.get("status")
    disputes = Dispute.objects.select_related("user", "agent", "transaction")

    if status_filter:
        disputes = disputes.filter(status=status_filter)

    context = {
        "disputes": disputes,
        "status_filter": status_filter,
    }
    return render(request, "admin_dashboard/disputes_list.html", context)


@login_required
@user_passes_test(is_admin_user)
def dispute_detail(request, pk):
    dispute = (
        Dispute.objects.select_related("user", "agent__profile", "transaction")
        .prefetch_related("messages__sender")
        .get(pk=pk)
    )
    messages = dispute.messages.all()

    if request.method == "POST":
        message = request.POST.get("message")
        action = request.POST.get("action")

        if message:
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=request.user,
                message=message,
            )

        if action in ["resolved", "rejected", "under_review"]:
            dispute.status = action
            dispute.save(update_fields=["status"])

        return redirect("admin_dashboard:admin_dispute_detail", pk=dispute.pk)

    context = {
        "dispute": dispute,
        "messages": messages,
    }
    return render(request, "admin_dashboard/dispute_detail.html", context)



@login_required
@user_passes_test(is_admin_user)
def resolve_dispute(request, dispute_id):
    dispute = get_object_or_404(Dispute, id=dispute_id)

    if dispute.status == 'resolved':
        messages.warning(request, "This dispute is already resolved.")
        return redirect('admin_dashboard:dispute_detail', dispute_id=dispute.id)

    transaction = dispute.transaction

    # Case: No linked transaction
    if not transaction:
        dispute.status = 'resolved'
        dispute.resolved_by = request.user
        dispute.resolved_at = timezone.now()
        dispute.save()
        messages.success(request, f"Dispute #{dispute.id} resolved (no transaction involved).")
        return redirect('admin_dashboard:dispute_detail', dispute_id=dispute.id)

    # Determine if user needs credit
    credit_user = False
    issue = (dispute.issue_type or "").strip().lower()

    # Only credit user for realistic escrow failures
    if transaction.transaction_type == "deposit":
        # In your P2P escrow, deposits are secure, so only "Other issue" might trigger manual credit
        if issue == "other issue":
            credit_user = True
    elif transaction.transaction_type == "withdrawal":
        if issue in ["wrong amount received", "other issue"]:
            credit_user = True
    elif transaction.transaction_type == "transfer":
        if issue in ["duplicate transfer", "transfer failed but funds deducted", "other issue"]:
            credit_user = True
        # "Incorrect recipient details" does NOT trigger automatic credit in escrow
        # "Money not received by recipient" also doesn't because escrow guarantees transfer

    # Credit user if needed
    if credit_user:
        wallet, _ = Wallet.objects.get_or_create(user=dispute.user)
        wallet.balance += transaction.amount
        wallet.save()

        # Optional: record a dispute credit transaction
        # Transaction.objects.create(
        #     user=dispute.user,
        #     transaction_type="dispute_credit",
        #     amount=transaction.amount,
        #     reference=f"Dispute #{dispute.id} resolution"
        # )

    # Mark dispute resolved
    dispute.status = 'resolved'
    dispute.resolved_by = request.user
    dispute.resolved_at = timezone.now()
    dispute.save()

    messages.success(
        request,
        f"Dispute #{dispute.id} resolved" + (f" and user credited ₦{transaction.amount:.2f}" if credit_user else "")
    )

    return redirect('admin_dashboard:dispute_detail', dispute_id=dispute.id)


@login_required
@user_passes_test(lambda u: u.is_staff)  # admin check
def analytics(request):
    # --- Total counts ---
    total_users = User.objects.count()
    total_agents = Profile.objects.filter(is_agent=True).count()
    total_disputes = Dispute.objects.count()
    total_open_disputes = Dispute.objects.filter(status__in=['pending','under_review']).count()
    total_deposits = DepositRequest.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    total_withdrawals = WithdrawalRequest.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0

    # --- Last 7 days chart data ---
    dates = [(now() - timedelta(days=i)).date() for i in reversed(range(7))]
    deposits_amounts = [
        DepositRequest.objects.filter(created_at__date=d, status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        for d in dates
    ]
    withdrawals_amounts = [
        WithdrawalRequest.objects.filter(created_at__date=d, status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        for d in dates
    ]
    disputes_counts = [
        Dispute.objects.filter(created_at__date=d).count()
        for d in dates
    ]

    # --- Top 5 agents by deposits processed ---
    # top_agents = Profile.objects.filter(is_agent=True).annotate(
    #     total_deposit=Sum('user_deposits__amount', filter=Q(user_deposits__status='completed'))
    # ).order_by('-total_deposit')[:5]

    context = {
        'total_users': total_users,
        'total_agents': total_agents,
        'total_disputes': total_disputes,
        'total_open_disputes': total_open_disputes,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'dates': [str(d) for d in dates],
        'deposits_amounts': deposits_amounts,
        'withdrawals_amounts': withdrawals_amounts,
        'disputes_counts': disputes_counts,
        # 'top_agents': top_agents,
    }

    return render(request, 'admin_dashboard/analytics.html', context)


@login_required
def analytics_chart_data(request):
    # Last 7 days
    today = datetime.now().date()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(7))]

    deposits_amounts = []
    withdrawals_amounts = []
    disputes_counts = []

    for d in dates:
        deposits_amounts.append(
            DepositRequest.objects.filter(created_at__date=d).aggregate(total=models.Sum('amount'))['total'] or 0
        )
        withdrawals_amounts.append(
            WithdrawalRequest.objects.filter(created_at__date=d).aggregate(total=models.Sum('amount'))['total'] or 0
        )
        disputes_counts.append(
            Dispute.objects.filter(created_at__date=d).count()
        )

    return JsonResponse({
        "dates": dates,
        "deposits_amounts": deposits_amounts,
        "withdrawals_amounts": withdrawals_amounts,
        "disputes_counts": disputes_counts,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)  # Only admin can access
def admin_settings(request):
    profile = request.user.profile

    if request.method == "POST":
        # Remove avatar
        if request.POST.get("remove_avatar"):
            if profile.avatar:
                profile.avatar.delete(save=True)
                messages.success(request, "Avatar removed successfully.")
            return redirect("admin_dashboard:admin_settings")

        # Update profile info
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        avatar = request.FILES.get("avatar")

        # Update User
        request.user.first_name = full_name  # Optional: split if you want first/last
        request.user.email = email
        request.user.save()

        # Update Profile
        profile.phone = phone
        if avatar:
            profile.avatar = avatar
        profile.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("admin_dashboard:admin_settings")

    context = {
        "user": request.user,
        "profile": profile
    }
    return render(request, "admin_dashboard/admin_settings.html", context)



@login_required
@user_passes_test(lambda u: u.is_superuser)
def system_settings(request):
    settings_obj, created = SystemSettings.objects.get_or_create(id=1)

    if request.method == "POST":
        data = request.POST
        settings_obj.transaction_fee_low = data.get("transaction_fee_low", settings_obj.transaction_fee_low)
        settings_obj.transaction_fee_high = data.get("transaction_fee_high", settings_obj.transaction_fee_high)
        settings_obj.split_platform = data.get("split_platform", settings_obj.split_platform)
        settings_obj.split_agent = data.get("split_agent", settings_obj.split_agent)
        settings_obj.escrow_expiry_minutes = data.get("escrow_expiry_minutes", settings_obj.escrow_expiry_minutes)
        settings_obj.min_transaction = data.get("min_transaction", settings_obj.min_transaction)
        settings_obj.max_transaction = data.get("max_transaction", settings_obj.max_transaction)
        settings_obj.kyc_required = "kyc_required" in data
        settings_obj.enable_2fa = "enable_2fa" in data
        settings_obj.fraud_detection_enabled = "fraud_detection_enabled" in data
        settings_obj.deposit_enabled = "deposit_enabled" in data
        settings_obj.withdrawal_enabled = "withdrawal_enabled" in data
        settings_obj.agent_auto_approval = "agent_auto_approval" in data
        settings_obj.maintenance_mode = "maintenance_mode" in data
        settings_obj.log_user_activity = "log_user_activity" in data
        settings_obj.support_email = data.get("support_email", settings_obj.support_email)
        settings_obj.support_phone = data.get("support_phone", settings_obj.support_phone)
        settings_obj.homepage_banner_text = data.get("homepage_banner_text", settings_obj.homepage_banner_text)
        settings_obj.backup_frequency_hours = data.get("backup_frequency_hours", settings_obj.backup_frequency_hours)
        settings_obj.save()

        messages.success(request, "System settings updated successfully.")
        return redirect("admin_dashboard:system_settings")

    return render(request, "admin_dashboard/system_settings.html", {"settings": settings_obj})
