from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.db import models

from .models import Wallet
from payments.models import Transaction
from accounts.utils import create_notification
from payments.forms import WithdrawalAmountForm, WithdrawalReceiptForm
from payments.models import WithdrawalRequest


# ✅ 1. Wallet Balance API
@login_required
@require_http_methods(["GET"])
def get_balance_api(request):
    try:
        wallet = request.user.wallet
        return JsonResponse({
            "balance": str(wallet.balance),
            "account_number": wallet.account_number,
            "updated_at": wallet.updated_at.isoformat(),
        })
    except Wallet.DoesNotExist:
        return JsonResponse({
            "balance": "0.00",
            "account_number": "N/A",
            "updated_at": timezone.now().isoformat(),
            "error": "Wallet not found",
        }, status=404)


# ✅ 2. Wallet Overview
@login_required
def wallet_overview(request):
    wallet = Wallet.objects.filter(user=request.user).first()
    balance = wallet.balance if wallet else Decimal("0.00")
    account_number = wallet.account_number if wallet else "N/A"

    recent_transactions = Transaction.objects.filter(
        models.Q(sender=wallet) | models.Q(receiver=wallet)
    ).order_by("-created_at")[:5] if wallet else []

    return render(request, "wallet/overview.html", {
        "wallet": wallet,
        "balance": balance,
        "account_number": account_number,
        "recent_transactions": recent_transactions,
    })


# ✅ 3. Lookup Account (AJAX endpoint)
@login_required
def lookup_account(request):
    account_number = request.GET.get("account_number")
    try:
        wallet = Wallet.objects.get(account_number=account_number)
        return JsonResponse({
            "success": True,
            "name": wallet.user.get_full_name() or wallet.user.username,
        })
    except Wallet.DoesNotExist:
        return JsonResponse({"success": False})


# ✅ 4. Send Money (transfer between wallets)
@login_required
def send_money(request):
    wallet = get_object_or_404(Wallet, user=request.user)

    if request.method == "POST":
        account_number = request.POST.get("account_number")
        amount_str = request.POST.get("amount", "0")
        description = request.POST.get("description", "")

        # Validate amount
        try:
            amount = Decimal(amount_str)
        except InvalidOperation:
            messages.error(request, "Invalid amount entered.")
            return redirect("wallet:send")

        if amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return redirect("wallet:send")

        if wallet.balance < amount:
            messages.error(request, "Insufficient funds.")
            return redirect("wallet:send")

        # Find recipient wallet
        recipient_wallet = Wallet.objects.filter(account_number=account_number).first()
        if not recipient_wallet:
            messages.error(request, "Recipient account not found.")
            return redirect("wallet:send")

        if recipient_wallet == wallet:
            messages.error(request, "You cannot send money to yourself.")
            return redirect("wallet:send")

        # Process transaction
        wallet.balance -= amount
        recipient_wallet.balance += amount
        wallet.save(update_fields=["balance", "updated_at"])
        recipient_wallet.save(update_fields=["balance", "updated_at"])

        # Record transaction
        Transaction.objects.create(
            sender=wallet,
            receiver=recipient_wallet,
            transaction_type="transfer",
            amount=amount,
            status="completed",
            description=description or f"Sent to {recipient_wallet.user.username}",
        )

        # Send notifications
        create_notification(request.user, "Money Sent", f"You sent ₦{amount} to {recipient_wallet.user.username}")
        create_notification(recipient_wallet.user, "Money Received", f"You received ₦{amount} from {request.user.username}")

        messages.success(request, f"₦{amount} sent successfully to {recipient_wallet.user.username}.")
        return redirect("wallet:overview")

    return render(request, "wallet/send_money.html", {"wallet": wallet})


# ✅ 5. Transaction History (with filters)
@login_required
def transaction_history(request):
    wallet = get_object_or_404(Wallet, user=request.user)
    transactions = Transaction.objects.filter(
        models.Q(sender=wallet) | models.Q(receiver=wallet)
    ).order_by("-created_at")

    tx_type = request.GET.get("type")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if tx_type:
        transactions = transactions.filter(transaction_type=tx_type)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
            transactions = transactions.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
            transactions = transactions.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass

    return render(request, "wallet/transaction_history.html", {
        "wallet": wallet,
        "transactions": transactions,
    })


# ✅ 6. Transaction Detail (view one transaction)
@login_required
def transaction_detail(request, transaction_id):
    wallet = get_object_or_404(Wallet, user=request.user)
    transaction = get_object_or_404(Transaction, transaction_id=transaction_id)

    if transaction.sender != wallet and transaction.receiver != wallet:
        return HttpResponseForbidden("You don’t have permission to view this transaction.")

    return render(request, "wallet/transaction_detail.html", {
        "transaction": transaction,
        "wallet": wallet,
    })



# @login_required
# def start_withdrawal(request):
#     """User initiates a withdrawal request."""
#     wallet = get_object_or_404(Wallet, user=request.user)

#     if request.method == "POST":
#         form = WithdrawalAmountForm(request.POST)
#         if form.is_valid():
#             amount = form.cleaned_data["amount"]

#             if wallet.balance < amount:
#                 messages.error(request, "Insufficient balance.")
#                 return redirect("start_withdrawal")

#             # Create withdrawal record
#             withdrawal = WithdrawalRequest.objects.create(
#                 user=request.user,
#                 amount=amount,
#                 status="pending",
#             )

#             create_notification(
#                 request.user,
#                 "Withdrawal Request Created",
#                 f"Your withdrawal of ₦{amount} is pending agent acceptance."
#             )
#             messages.success(request, "Withdrawal request created successfully.")
#             return redirect("user_withdrawal_list")
#     else:
#         form = WithdrawalAmountForm()

#     return render(request, "dashboard/withdrawal.html", {"form": form, "wallet": wallet})


@login_required
def user_withdrawal_list(request):
    """List user's withdrawal requests."""
    withdrawals = WithdrawalRequest.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "dashboard/withdrawal_list.html", {"withdrawals": withdrawals})
