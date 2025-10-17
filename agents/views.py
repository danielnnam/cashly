from decimal import Decimal
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
from accounts.models import Profile
from django.contrib.auth import login, logout, authenticate
from admin_dashboard.utils import log_activity  

# Create your views here.

@login_required
def agent_dashboard(request):
    """Agent Dashboard showing key metrics and latest requests"""
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



def logout_view(request):
    """Simple logout view"""
    logout(request)
    return redirect('home')