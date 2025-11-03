from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class ActivityLog(models.Model):
    ACTIVITY_TYPES = [
        ("user_registration", "User Registration"),
        ("transaction", "Transaction"),
        ("dispute", "Dispute"),
        ("agent_application", "Agent Application"),
        ("system", "System"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("review", "Review"),
        ("open", "Open"),
    ]

    type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    icon = models.CharField(max_length=50, default="info-circle")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_type_display()})"

    @property
    def time_ago(self):
        from django.utils.timesince import timesince
        return timesince(self.created_at) + " ago"



class AdminNotification(models.Model):
    """Notifications visible only to admin users."""
    title = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="admin_notifications")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.admin_user.username}"




class SystemSettings(models.Model):
    # 💰 Transaction & Fee Settings
    transaction_fee_low = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    transaction_fee_high = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    split_platform = models.DecimalField(max_digits=5, decimal_places=2, default=60.00)
    split_agent = models.DecimalField(max_digits=5, decimal_places=2, default=40.00)
    escrow_expiry_minutes = models.PositiveIntegerField(default=15)
    min_transaction = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    max_transaction = models.DecimalField(max_digits=12, decimal_places=2, default=500000.00)

    # 🔒 Security Settings
    kyc_required = models.BooleanField(default=True)
    max_daily_transactions = models.PositiveIntegerField(default=10)
    max_daily_amount = models.DecimalField(max_digits=12, decimal_places=2, default=1000000.00)
    enable_2fa = models.BooleanField(default=False)
    fraud_detection_enabled = models.BooleanField(default=True)

    # ⚙️ Platform Control
    deposit_enabled = models.BooleanField(default=True)
    withdrawal_enabled = models.BooleanField(default=True)
    agent_auto_approval = models.BooleanField(default=False)
    maintenance_mode = models.BooleanField(default=False)
    support_email = models.EmailField(default="support@cashly.com")
    support_phone = models.CharField(max_length=20, default="+2340000000000")
    homepage_banner_text = models.CharField(max_length=255, blank=True, null=True)

    # 🧾 System Monitoring
    log_user_activity = models.BooleanField(default=True)
    backup_frequency_hours = models.PositiveIntegerField(default=24)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "System Settings"

    class Meta:
        verbose_name_plural = "System Settings"