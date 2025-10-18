# payments/views.py
from django.urls import reverse
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse, Http404
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import get_user_model

from accounts.models import Profile
from accounts.utils import create_notification
from admin_dashboard.utils import log_activity
from wallet.models import Wallet
from .models import DepositRequest, WithdrawalRequest
from .forms import (
    ReceiptUploadForm, DepositAmountForm,
    WithdrawalAmountForm, WithdrawalReceiptForm
)
from django.db import transaction


User = get_user_model()


# ============================================================
# ✅ USER DASHBOARD — View All My Requests (Deposit + Withdrawal)
# ============================================================

@login_required
def users_request_list(request):
    """
    Unified list of all user's deposit and withdrawal requests.
    Supports filters (type & status) + AJAX updates.
    """
    user = request.user
    now = timezone.now()
    req_type = request.GET.get("type")  # deposit / withdrawal
    status = request.GET.get("status")

    # Expire stale accepted requests
    for dep in DepositRequest.objects.filter(status="accepted", expires_at__lt=now):
        try:
            dep.expire()
        except Exception:
            pass

    for w in WithdrawalRequest.objects.filter(status="accepted", expires_at__lt=now):
        try:
            w.expire()
        except Exception:
            pass

    # Combine deposits & withdrawals
    deposits = DepositRequest.objects.filter(user=user)
    withdrawals = WithdrawalRequest.objects.filter(user=user)

    # Optional filters
    if status:
        deposits = deposits.filter(status=status)
        withdrawals = withdrawals.filter(status=status)

    # Add req_type field manually
    for d in deposits:
        d.req_type = "deposit"
    for w in withdrawals:
        w.req_type = "withdrawal"

    # Combine both types into one list
    all_requests = []
    if not req_type or req_type == "deposit":
        all_requests += list(deposits)
    if not req_type or req_type == "withdrawal":
        all_requests += list(withdrawals)

    # Sort by date (most recent first)
    all_requests.sort(key=lambda x: x.created_at, reverse=True)

    context = {
        "requests": all_requests,
        "req_type": req_type,
        "status": status,
        "status_filters": ["pending", "accepted", "completed", "expired", "cancelled"],
        "type_filters": ["deposit", "withdrawal"],
    }

    # AJAX support (if requested dynamically)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "payments/users_request_list.html", context)

    return render(request, "payments/users_request_list.html", context)





# ============================================================
# ✅ USER DEPOSIT REQUEST FLOW
# ============================================================

@login_required
def start_deposit(request):
    """Step 1 - User chooses deposit amount"""
    if request.method == "POST":
        form = DepositAmountForm(request.POST)
        if form.is_valid():
            request.session["deposit_amount"] = str(form.cleaned_data["amount"])
            return redirect("payments:choose_agent")
    else:
        form = DepositAmountForm()
    return render(request, "payments/start_deposit.html", {"form": form})


@login_required
def choose_agent(request):
    """Step 2 - User chooses an agent for deposit"""
    amount = request.session.get("deposit_amount")
    if not amount:
        return redirect("payments:start_deposit")

    agents = Profile.objects.filter(is_agent=True).exclude(user=request.user).select_related("user")

    for agent in agents:
        completed_deposits = DepositRequest.objects.filter(agent=agent.user, status="completed").count()
        completed_withdrawals = WithdrawalRequest.objects.filter(agent=agent.user, status="completed").count()
        total_completed = completed_deposits + completed_withdrawals

        total_assigned = (
            DepositRequest.objects.filter(agent=agent.user).count() +
            WithdrawalRequest.objects.filter(agent=agent.user).count()
        )

        completion_rate = (total_completed / total_assigned * 100) if total_assigned > 0 else 0
        agent.completed_trades = total_completed
        agent.completion_rate = round(completion_rate, 1)

    return render(request, "payments/choose_agent.html", {
        "amount": amount,
        "agents": agents,
    })


@login_required
@require_POST
def create_deposit(request):
    """Step 3 - Create deposit request"""
    agent_id = request.POST.get("agent")
    amount = request.POST.get("amount")

    if not agent_id or not amount:
        messages.error(request, "Select an agent and amount.")
        return redirect("payments:choose_agent")

    try:
        amount_dec = Decimal(amount)
        if amount_dec <= 0:
            raise InvalidOperation
    except InvalidOperation:
        messages.error(request, "Invalid amount.")
        return redirect("payments:choose_agent")

    wallet = getattr(request.user, "wallet", None)
    if not wallet:
        messages.error(request, "No wallet found; contact support.")
        return redirect("dashboard")

    agent_profile = get_object_or_404(Profile, pk=agent_id, is_agent=True)
    if agent_profile.user == request.user:
        messages.error(request, "You cannot select yourself as an agent.")
        return redirect("payments:choose_agent")

    dep = DepositRequest.objects.create(
        wallet=wallet,
        user=request.user,
        agent=agent_profile.user,
        amount=amount_dec,
        reference=DepositRequest.generate_reference(wallet),
        status="pending"
    )
    log_activity(
        user=request.user,
        title="Deposit Request Created",
        description=f"₦{Decimal(amount):,.2f} deposit request sent to agent {agent_profile.user.username}",
        type="transaction",
        status="pending",
        icon="arrow-down"
    )




    messages.success(request, f"Deposit request {dep.reference} created. Await agent acceptance.")
    return redirect("payments:user_deposit_detail", reference=dep.reference)


@login_required
def user_deposit_detail(request, reference):
    """Step 4 - User views deposit details"""
    dep = get_object_or_404(DepositRequest, reference=reference, user=request.user)

    # Auto-expire if needed
    if dep.status == "accepted" and dep.expires_at and timezone.now() > dep.expires_at:
        dep.expire()

    return render(request, "payments/user_deposit_detail.html", {"deposit": dep, "request_obj": dep})


@login_required
@require_POST
def mark_as_paid_request(request, reference):
    """User clicks 'I Have Paid'"""
    dep = get_object_or_404(DepositRequest, reference=reference, user=request.user)

    if dep.status != "accepted":
        messages.error(request, "You can only mark as paid after an agent accepts.")
        return redirect("payments:user_deposit_detail", reference=reference)

    receipt = request.FILES.get("receipt")
    ok = dep.mark_as_paid(receipt_file=receipt)
    if ok:
        if dep.agent:
            create_notification(dep.agent, "Buyer marked as paid", f"{request.user.username} marked {dep.reference} as paid.")
        messages.success(request, "Marked as paid. Agent will confirm soon.")
    else:
        messages.error(request, "Could not mark as paid.")
    return redirect("payments:user_deposit_detail", reference=reference)



@login_required
def upload_receipt(request, reference):
    """
    Handles upload of payment receipts (for both Deposits and Withdrawals)
    by either users or agents.
    """
    # Try Deposit first, then Withdrawal
    try:
        req = DepositRequest.objects.get(reference=reference)
        req_type = "deposit"
    except DepositRequest.DoesNotExist:
        try:
            req = WithdrawalRequest.objects.get(reference=reference)
            req_type = "withdrawal"
        except WithdrawalRequest.DoesNotExist:
            raise Http404("Request not found")

    # Ensure only the rightful participant can upload
    if req.user != request.user and getattr(req, "agent", None) != request.user:
        return HttpResponseForbidden("You are not allowed to upload for this transaction")

    if request.method == "POST" and request.FILES.get("receipt"):
        receipt = request.FILES["receipt"]
        req.receipt = receipt
        req.save()

        messages.success(request, "Receipt uploaded successfully!")
        if req_type == "deposit":
            return redirect("payments:user_deposit_detail", reference=req.reference)
        else:
            return redirect("payments:withdrawal_detail", reference=req.reference)

    return render(
        request,
        "payments/upload_receipt.html",
        {"request_obj": req, "request_type": req_type},
    )




# ============================================================
# ✅ WITHDRAWAL FLOW
# ============================================================

@login_required
def start_withdrawal(request):
    """Step 1 - User initiates withdrawal"""
    wallet = getattr(request.user, "wallet", None)
    if not wallet:
        messages.error(request, "No wallet found.")
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = WithdrawalAmountForm(request.POST)
        if form.is_valid():
            request.session["withdrawal_amount"] = str(form.cleaned_data["amount"])
            return redirect("payments:choose_agent_withdrawal")
    else:
        form = WithdrawalAmountForm()
    return render(request, "wallet/start_withdrawal.html", {"form": form, "wallet": wallet})


@login_required
def choose_agent_withdrawal(request):
    """Step 2 - Choose agent for withdrawal"""
    amount = request.session.get("withdrawal_amount")
    if not amount:
        return redirect("payments:start_withdrawal")

    agents = Profile.objects.filter(is_agent=True).exclude(user=request.user).select_related("user")

    for agent in agents:
        completed_deposits = DepositRequest.objects.filter(agent=agent.user, status="completed").count()
        completed_withdrawals = WithdrawalRequest.objects.filter(agent=agent.user, status="completed").count()
        total_completed = completed_deposits + completed_withdrawals

        total_assigned = (
            DepositRequest.objects.filter(agent=agent.user).count() +
            WithdrawalRequest.objects.filter(agent=agent.user).count()
        )

        completion_rate = (total_completed / total_assigned * 100) if total_assigned > 0 else 0
        agent.completed_trades = total_completed
        agent.completion_rate = round(completion_rate, 1)

    return render(request, "wallet/choose_agent_withdrawal.html", {
        "amount": amount,
        "agents": agents,
    })


@login_required
@require_POST
def create_withdrawal(request):
    """Step 3 - Create withdrawal request"""
    agent_id = request.POST.get("agent")
    amount = request.POST.get("amount") or request.session.get("withdrawal_amount")
    if not agent_id or not amount:
        messages.error(request, "Select an agent and amount.")
        return redirect("payments:choose_agent_withdrawal")

    amount_dec = Decimal(amount)
    wallet = getattr(request.user, "wallet", None)
    if not wallet:
        messages.error(request, "No wallet found.")
        return redirect("dashboard")

    agent_profile = get_object_or_404(Profile, pk=agent_id, is_agent=True)
    if agent_profile.user == request.user:
        messages.error(request, "You cannot select yourself as an agent.")
        return redirect("payments:choose_agent_withdrawal")

    w = WithdrawalRequest.objects.create(
        wallet=wallet,
        user=request.user,
        agent=agent_profile.user,
        amount=amount_dec,
        reference=WithdrawalRequest.generate_reference(wallet),
        status="pending"
    )
    log_activity(
        user=request.user,
        title="Withdrawal Request Created",
        description=f"Withdrawal of ₦{amount_dec:,} requested with agent {agent_profile.user.username}",
        type="transaction",
        status="pending",
        icon="arrow-up"
    )



    create_notification(w.user, "Withdrawal Requested", f"Your withdrawal {w.reference} is pending agent acceptance.")
    messages.success(request, f"Withdrawal request {w.reference} created. Await agent acceptance.")
    return redirect("payments:withdrawal_detail", reference=w.reference)


# ============================================================
# ✅ AGENT PAGES (Handles Both Deposit + Withdrawal)
# ============================================================

@login_required
def agent_request_list(request):
    """Show both deposit and withdrawal requests"""
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_agent:
        return HttpResponseForbidden("Only agents allowed")

    status = request.GET.get("status")

    for req in DepositRequest.objects.filter(status="accepted", expires_at__lt=timezone.now()):
        req.expire()
    for req in WithdrawalRequest.objects.filter(status="accepted", expires_at__lt=timezone.now()):
        req.expire()

    deposits = DepositRequest.objects.filter(
        Q(status="pending", agent__isnull=True) | Q(agent=request.user)
    ).order_by("-created_at")

    withdrawals = WithdrawalRequest.objects.filter(
        Q(status="pending", agent__isnull=True) | Q(agent=request.user)
    ).order_by("-created_at")

    for d in deposits:
        d.request_type = "deposit"
    for w in withdrawals:
        w.request_type = "withdrawal"

    all_requests = sorted(list(deposits) + list(withdrawals), key=lambda x: x.created_at, reverse=True)

    if status:
        all_requests = [r for r in all_requests if r.status == status]

    return render(request, "payments/agent_request_list.html", {"requests": all_requests})


@login_required
def agent_request_detail(request, reference):
    """Unified agent request detail page"""
    profile = getattr(request.user, "profile", None)
    if not profile or not getattr(profile, "is_agent", False):
        return HttpResponseForbidden("Only agents allowed")

    # Find either deposit or withdrawal request
    req = (
        DepositRequest.objects.filter(reference=reference).first()
        or WithdrawalRequest.objects.filter(reference=reference).first()
    )
    if not req:
        raise Http404("Request not found")

    # Expire if past expiration date
    if req.status == "accepted" and getattr(req, "expires_at", None) and timezone.now() > req.expires_at:
        req.expire()

    req_type = "deposit" if isinstance(req, DepositRequest) else "withdrawal"

    # Bank details are only shown for withdrawals that are accepted or paid
    show_bank_details = req_type == "withdrawal" and req.status in ["accepted", "paid"]

    # Show deposit details flag
    show_deposit_details = req_type == "deposit"

    context = {
        "request_obj": req,
        "req_type": req_type,
        "show_bank_details": show_bank_details,
        "show_deposit_details": show_deposit_details,
    }

    return render(request, "payments/agent_request_detail.html", context)


@login_required
@require_POST
def agent_take_request(request, reference):
    """
    Agent accepts a pending deposit or withdrawal request.
    Works for both deposit and withdrawal types.
    """

    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_agent:
        return HttpResponseForbidden("Only agents are allowed.")

    # Find the request (deposit or withdrawal)
    req = DepositRequest.objects.filter(reference=reference).first() \
          or WithdrawalRequest.objects.filter(reference=reference).first()

    if not req:
        messages.error(request, "Request not found.")
        return redirect("payments:agent_request_list")

    if req.status != "pending":
        messages.error(request, "Request is not available to take.")
        return redirect("payments:agent_request_detail", reference=reference)

    # Accept request (deposit or withdrawal)
    accepted = req.accept(request.user, countdown_minutes=15)

    if not accepted:
        messages.error(request, "Could not accept request. Check balances or request status.")
        return redirect("payments:agent_request_detail", reference=reference)

    create_notification(
        req.user,
        "Agent Accepted",
        f"{request.user.username} accepted your request {req.reference}"
    )
    log_activity(
        user=req.user,
        title="Agent Accepted Deposit Request",
        description=f"Agent {request.user.username} accepted deposit request {req.reference}",
        type="deposit",
        status="pending",
        icon="handshake"
    )



    messages.success(request, "You accepted the request — countdown started.")
    return redirect("payments:agent_request_detail", reference=req.reference)



@login_required
def agent_confirm_request(request, reference):
    req = get_object_or_404(DepositRequest, reference=reference)
    profile = request.user.profile

    if not profile.is_agent:
        return HttpResponseForbidden("Only agents can confirm deposits")

    success = req.confirm(agent_user=request.user)
    if success:
        messages.success(request, "Deposit confirmed successfully.")
    else:
        messages.error(request, "Deposit could not be confirmed.")

    return redirect("payments:agent_request_detail", reference=reference)




# ============================================================
# ✅ MISSING VIEWS COMPLETED BELOW
# ============================================================

@login_required
def withdrawal_detail(request, reference):
    """User views withdrawal details"""
    w = get_object_or_404(WithdrawalRequest, reference=reference, user=request.user)

    # Auto-expire if countdown ended
    if w.status == "accepted" and w.expires_at and timezone.now() > w.expires_at:
        w.expire()

    return render(
        request,
        "wallet/user_withdrawal_detail.html",
        {"withdrawal": w, "request_obj": w}
    )


@login_required
@require_POST
def user_confirm_withdrawal(request, reference):
    withdrawal = get_object_or_404(WithdrawalRequest, reference=reference, user=request.user)

    if withdrawal.status != "paid":
        messages.error(request, "Withdrawal is not ready to be confirmed.")
        return redirect(reverse("payments:withdrawal_detail", args=[reference]))

    success = withdrawal.confirm(user=request.user)

    if success:
        messages.success(request, "Withdrawal confirmed successfully.")
    else:
        messages.error(request, "Failed to confirm withdrawal.")

    return redirect(reverse("payments:withdrawal_detail", args=[reference]))


@login_required
@require_POST
def agent_mark_withdrawal_paid(request, reference):
    withdrawal = get_object_or_404(WithdrawalRequest, reference=reference)

    if withdrawal.agent != request.user:
        messages.error(request, "You are not authorized to mark this withdrawal as paid.")
        return redirect(reverse("payments:agent_request_detail", args=[reference]))

    if withdrawal.status != "accepted":
        messages.error(request, "Withdrawal is not in a state to be marked as paid.")
        return redirect(reverse("payments:agent_request_detail", args=[reference]))

    success = withdrawal.mark_as_paid(agent_user=request.user, receipt_file=request.FILES.get("receipt"))

    if success:
        messages.success(request, "Withdrawal marked as paid successfully.")
    else:
        messages.error(request, "Failed to mark withdrawal as paid.")

    # Adjusted log_activity call
    log_activity(
        user=request.user,  # the actor performing the action
        action="Marked withdrawal as paid",
        description=f"Agent {request.user.username} marked withdrawal {withdrawal.reference} as paid.",
        reference=withdrawal.reference,
        activity_type="withdrawal"
    )

    return redirect(reverse("payments:agent_request_detail", args=[reference]))


@login_required
def user_request_detail(request, reference):
    """Fallback: view withdrawal request detail (used in redirect)"""
    # Try both deposit and withdrawal references
    req = DepositRequest.objects.filter(reference=reference, user=request.user).first() or \
          WithdrawalRequest.objects.filter(reference=reference, user=request.user).first()
    if not req:
        raise Http404("Request not found")

    req_type = "deposit" if isinstance(req, DepositRequest) else "withdrawal"
    return render(request, "payments/user_request_detail.html", {"request_obj": req, "req_type": req_type})

