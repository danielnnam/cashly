from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Wallet, Transaction, Beneficiary, PaymentRequest
from .models import Dispute, DisputeMessage


class WalletInline(admin.StackedInline):
    model = Wallet
    can_delete = False
    verbose_name_plural = 'Wallet'
    readonly_fields = ['account_number', 'created_at', 'updated_at']

class CustomUserAdmin(UserAdmin):
    inlines = [WalletInline]

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'user', 'balance', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['account_number', 'user__username', 'user__email']
    readonly_fields = ['account_number', 'created_at', 'updated_at']
    actions = ['activate_wallets', 'deactivate_wallets']
    
    def activate_wallets(self, request, queryset):
        queryset.update(is_active=True)
    activate_wallets.short_description = "Activate selected wallets"
    
    def deactivate_wallets(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_wallets.short_description = "Deactivate selected wallets"

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'transaction_type', 'amount', 'status', 'created_at')
    list_filter = ('status', 'transaction_type', 'created_at')
    list_editable = ('status',)


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_number', 'account_name', 'bank_name', 'is_active']
    list_filter = ['bank_name', 'is_active', 'created_at']
    search_fields = ['account_number', 'account_name', 'user__username']

@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ['requester', 'recipient', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['requester__username', 'recipient__username']



class DisputeMessageInline(admin.TabularInline):
    model = DisputeMessage
    extra = 0
    readonly_fields = ("sender", "message", "timestamp")

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "user", "agent", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("subject", "user__username", "agent__username")
    inlines = [DisputeMessageInline]