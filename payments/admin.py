# payments/admin.py
from django.contrib import admin
from django.db import transaction
from .models import DepositRequest, Escrow
from accounts.utils import create_notification
from wallet.models import Wallet, Transaction
from decimal import Decimal
from django.utils import timezone


@admin.register(DepositRequest)
class DepositRequestAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'wallet',
        'user',
        'agent',
        'amount',
        'status',
        'created_at',
        'accepted_at',
        'confirmed_at',
        'completed_at',
        'expires_at',
    )
    list_filter = ('status', 'created_at', 'accepted_at', 'completed_at')
    search_fields = (
        'reference',
        'wallet__user__username',
        'wallet__account_number',
        'agent__username',
    )
    readonly_fields = (
        'reference',
        'wallet',
        'user',
        'agent',
        'amount',
        'status',
        'created_at',
        'accepted_at',
        'confirmed_at',
        'completed_at',
        'expires_at',
    )

    actions = ["force_release_escrow", "force_refund_escrow"]

    def force_release_escrow(self, request, queryset):
        """
        Admin manually releases escrow:
        - Credits user wallet
        - Pays commission (if configured)
        - Sends notification
        """
        released_count = 0
        with transaction.atomic():
            for dep in queryset.select_for_update():
                escrow = getattr(dep, "escrow", None)
                if escrow and escrow.status == "holding":
                    ok, msg = escrow.release(agent_user=dep.agent)
                    if ok:
                        released_count += 1
                        create_notification(
                            dep.wallet.user,
                            "Deposit Released",
                            f"Admin has forcefully released your deposit ₦{dep.amount} ({dep.reference})."
                        )
        self.message_user(request, f"{released_count} escrow(s) force-released.")

    force_release_escrow.short_description = "Force release escrow (mark as completed)"

    def force_refund_escrow(self, request, queryset):
        """
        Admin manually refunds escrow:
        - Expires the deposit
        - Sends notification
        """
        refunded_count = 0
        with transaction.atomic():
            for dep in queryset.select_for_update():
                escrow = getattr(dep, "escrow", None)
                if escrow and escrow.status == "holding":
                    ok, msg = escrow.refund()
                    if ok:
                        refunded_count += 1
                        create_notification(
                            dep.wallet.user,
                            "Deposit Refunded",
                            f"Admin has refunded your deposit ₦{dep.amount} ({dep.reference})."
                        )
        self.message_user(request, f"{refunded_count} escrow(s) force-refunded.")

    force_refund_escrow.short_description = "Force refund escrow (mark as expired)"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Only allow "view", not inline editing
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Escrow)
class EscrowAdmin(admin.ModelAdmin):
    list_display = ('deposit_request', 'amount', 'commission', 'status', 'created_at', 'released_at', 'refunded_at')
    list_filter = ('status', 'created_at')
    search_fields = ('deposit_request__reference', 'deposit_request__user__username')
    readonly_fields = (
        'deposit_request',
        'amount',
        'commission',
        'status',
        'created_at',
        'released_at',
        'refunded_at',
    )

    actions = ["admin_release", "admin_refund"]

    def admin_release(self, request, queryset):
        released_count = 0
        with transaction.atomic():
            for esc in queryset.select_for_update():
                if esc.status == "holding":
                    ok, msg = esc.release(agent_user=esc.deposit_request.agent)
                    if ok:
                        released_count += 1
                        create_notification(
                            esc.deposit_request.wallet.user,
                            "Escrow Released",
                            f"Admin has released your escrow ₦{esc.amount} ({esc.deposit_request.reference})."
                        )
        self.message_user(request, f"{released_count} escrow(s) released.")

    admin_release.short_description = "Release escrow (credit wallet)"

    def admin_refund(self, request, queryset):
        refunded_count = 0
        with transaction.atomic():
            for esc in queryset.select_for_update():
                if esc.status == "holding":
                    ok, msg = esc.refund()
                    if ok:
                        refunded_count += 1
                        create_notification(
                            esc.deposit_request.wallet.user,
                            "Escrow Refunded",
                            f"Admin has refunded your escrow ₦{esc.amount} ({esc.deposit_request.reference})."
                        )
        self.message_user(request, f"{refunded_count} escrow(s) refunded.")

    admin_refund.short_description = "Refund escrow (expire deposit)"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
