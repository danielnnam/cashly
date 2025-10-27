from datetime import timezone
from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import AgentApplicationForm
from .models import AgentApplication
from django.db.models import Sum, Count, Q, F
from payments.models import DepositRequest, Transaction
from wallet.models import Wallet
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from accounts.models import Notification, Profile
from django.contrib.auth import login, logout, authenticate
from admin_dashboard.utils import log_activity  
from django.contrib import messages
from wallet.models import Dispute, DisputeMessage

# Create your views here.

@login_required
def agent_dashboard(request):
    """Agent Dashboard showing key metrics and latest requests"""
    profile = request.user.profile

    if profile.is_suspended:
        messages.warning(request, "Your agent account is suspended.")
        return redirect('agents:suspension_notice')

    agent = request.user
    wallet = getattr(agent, "wallet", None)

    # Basic wallet info
    wallet_balance = wallet.balance if wallet else Decimal("0.00")

    # Request stats
    pending_requests = DepositRequest.objects.filter(agent=agent, status="pending").count()
    completed_requests = DepositRequest.objects.filter(agent=agent, status="completed").count()
    expired_requests = DepositRequest.objects.filter(agent=agent, status="expired").count()

    # Total requests (transactions handled by agent)
    total_requests = DepositRequest.objects.filter(agent=agent).count()

    # Success rate
    success_rate = round((completed_requests / total_requests) * 100, 1) if total_requests > 0 else 0

    # Recent 5 deposit requests
    recent_requests = DepositRequest.objects.filter(agent=agent).order_by("-created_at")[:5]

    # Full transaction history for table
    transactions = DepositRequest.objects.filter(agent=agent).order_by("-created_at")

    context = {
        "wallet_balance": wallet_balance,
        "pending_requests": pending_requests,
        "completed_requests": completed_requests,
        "expired_requests": expired_requests,
        "total_requests": total_requests,
        "success_rate": success_rate,
        "recent_requests": recent_requests,
        "transactions": transactions,
    }
    return render(request, "agents/dashboard.html", context)


@login_required
def suspension_notice(request):
    profile = request.user.profile

    if not profile.is_suspended:
        return redirect('agents:dashboard')  

    return render(request, "agents/suspension_notice.html", {"profile": profile})


@login_required
def appeal_suspension(request):
    profile = request.user.profile

    if request.method == "POST":
        appeal_text = request.POST.get("appeal_text")
        profile.suspension_appeal = appeal_text
        profile.appeal_status = "pending"
        profile.save()
        messages.success(request, "Your appeal has been submitted. The admin will review it soon.")
    return redirect("agents:suspension_notice")


@login_required
def become_agent(request):
    # Check if user has already applied
    existing_app = AgentApplication.objects.filter(user=request.user).last()

    if request.method == "POST":
        form = AgentApplicationForm(request.POST)
        if form.is_valid():
            # Prevent duplicate if already pending/approved
            if existing_app and existing_app.status in ["pending", "approved"]:
                messages.warning(request, "You already have an active application.")
                return redirect("agents:become_agent")

            agent_app = form.save(commit=False)
            agent_app.user = request.user
            agent_app.save()
            log_activity(
                user=request.user,
                title="New Agent Application",
                description=f"{request.user.username} submitted a new agent application.",
                type="agent_application",
                status="pending",
                icon="id-card"
            )
            messages.success(request, "Your application has been submitted successfully!")
            return redirect("agents:become_agent")
    else:
        form = AgentApplicationForm()

    return render(request, "agents/become_agent.html", {"form": form, "existing_app": existing_app})


from django.db.models import Q

@login_required
def agent_wallet(request):
    wallet = Wallet.objects.get(user=request.user)
    
    # Combine sent and received transactions
    transactions = Transaction.objects.filter(
        Q(sender=wallet) | Q(receiver=wallet)
    ).order_by('-created_at')[:10]
    
    context = {
        'wallet': wallet,
        'total_earned': getattr(wallet, 'total_earned', 0),
        'withdrawable': getattr(wallet, 'withdrawable_balance', 0),
        'transactions': transactions,
    }
    return render(request, 'agents/agent_wallet.html', context)


@login_required
def agent_history(request):
    profile = get_object_or_404(Profile, user=request.user, is_agent=True)
    wallet = get_object_or_404(Wallet, user=request.user)

    transactions = Transaction.objects.filter(
        Q(sender=wallet) | Q(receiver=wallet)
    ).order_by('-created_at')

    # 🔍 Filters
    search = request.GET.get('search')
    tx_type = request.GET.get('type')
    status = request.GET.get('status')

    if search:
        transactions = transactions.filter(
            Q(transaction_id__icontains=search) |
            Q(sender__user__username__icontains=search) |
            Q(receiver__user__username__icontains=search) |
            Q(sender__user__first_name__icontains=search) |
            Q(receiver__user__first_name__icontains=search)
        )

    if tx_type:
        transactions = transactions.filter(transaction_type=tx_type)

    if status:
        transactions = transactions.filter(status=status)

    context = {
        'transactions': transactions,
        'wallet': wallet,
    }
    return render(request, 'agents/history.html', context)



@login_required
def agent_dispute_list(request):
    # Get status filter from query params
    status_filter = request.GET.get('status')

    # Filter disputes assigned to this agent
    disputes = Dispute.objects.filter(agent=request.user)

    if status_filter:
        disputes = disputes.filter(status=status_filter)

    disputes = disputes.order_by('-created_at')

    # List of all possible statuses for filter links
    status_filters = ['pending', 'under_review', 'resolved', 'rejected']

    context = {
        'disputes': disputes,
        'status_filter': status_filter,
        'status_filters': status_filters,
    }
    return render(request, 'agents/disputes_list.html', context)


@login_required
def agent_dispute_detail(request, dispute_id):
    dispute = get_object_or_404(Dispute, id=dispute_id, agent=request.user)

    # --- AJAX Polling for new messages ---
    if request.GET.get("ajax") == "true":
        messages = DisputeMessage.objects.filter(dispute=dispute).order_by("timestamp")
        messages_data = [
            {
                "sender": "You" if msg.sender == request.user else msg.sender.username,
                "is_agent": msg.sender == dispute.agent,
                "is_user": msg.sender == dispute.user,
                "is_admin": msg.sender.is_staff,
                "message": msg.message,
                "timestamp": timezone.localtime(msg.timestamp).strftime("%b %d, %Y %H:%M"),
            }
            for msg in messages
        ]
        return JsonResponse({"messages": messages_data})

    # --- Handle POST actions ---
    if request.method == "POST":
        action = request.POST.get("action")
        message_text = request.POST.get("message")

        # Send message
        if message_text:
            DisputeMessage.objects.create(
                dispute=dispute, sender=request.user, message=message_text
            )

        # Update status (optional)
        if action in ["resolved", "under_review", "rejected"]:
            dispute.status = action
            dispute.save()

    messages = DisputeMessage.objects.filter(dispute=dispute).order_by("timestamp")
    return render(request, "agents/disputes_detail.html", {"dispute": dispute, "messages": messages})




def logout_view(request):
    """Simple logout view"""
    logout(request)
    return redirect('home')