from django.contrib import admin
from django.shortcuts import redirect
from wallet.models import Transaction

# Override admin homepage
admin.site.index_template = None

def custom_admin_index(request):
    return redirect("admin_dashboard")

admin.site.index = custom_admin_index


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'wallet', 'transaction_type', 'amount', 'status', 'created_at')
    search_fields = ('reference', 'wallet__user__username')
    list_filter = ('transaction_type', 'status', 'created_at')