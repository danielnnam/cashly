from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
import string
import secrets
from decimal import Decimal


# ======================
# 🏦 WALLET MODEL
# ======================
class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    account_number = models.CharField(max_length=10, unique=True, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    locked_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    # Optional Paystack fields
    paystack_customer_code = models.CharField(max_length=100, blank=True, null=True)
    paystack_account_id = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wallet"
        verbose_name_plural = "Wallets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - ₦{self.balance}"

    def save(self, *args, **kwargs):
        """Auto-generate account number on first save."""
        if not self.account_number:
            self.account_number = self.generate_account_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_account_number():
        """Generate a unique 10-digit account number."""
        while True:
            number = "".join(secrets.choice(string.digits) for _ in range(10))
            if not Wallet.objects.filter(account_number=number).exists():
                return number

    def can_transfer(self, amount: Decimal):
        """Check if this wallet has enough available funds."""
        return self.is_active and amount <= self.available_balance

    @property
    def available_balance(self):
        """Funds not locked or on hold."""
        return self.balance - self.locked_balance

    def get_transaction_history(self):
        """All transactions for this wallet."""
        return Transaction.objects.filter(
            Q(sender=self) | Q(receiver=self)
        ).order_by("-created_at")
    
    def debit(self, amount):
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False

    def credit(self, amount):
        self.balance += amount
        self.save()


# ======================
# 💳 TRANSACTION MODEL
# ======================
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("transfer", "Transfer"),
        ("deposit", "Deposit"),
        ("withdrawal", "Withdrawal"),
        ("payment", "Payment"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    transaction_id = models.CharField(max_length=20, unique=True, blank=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)

    sender = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="sent_transactions", null=True, blank=True
    )
    receiver = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="received_transactions", null=True, blank=True
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["sender", "receiver"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.transaction_id} - {self.transaction_type} - ₦{self.amount}"

    def save(self, *args, **kwargs):
        """Auto-generate transaction ID."""
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_transaction_id():
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        random_str = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        return f"TX{timestamp}{random_str}"

    def mark_completed(self):
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def mark_failed(self, reason=""):
        self.status = "failed"
        if reason:
            self.description = f"{self.description} | Failed: {reason}"
        self.save(update_fields=["status", "description", "updated_at"])


# ======================
# 👥 BENEFICIARY MODEL
# ======================
class Beneficiary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="beneficiaries")
    account_number = models.CharField(max_length=10)
    account_name = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=100, default="Cashly")
    nickname = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Beneficiary"
        verbose_name_plural = "Beneficiaries"
        unique_together = ["user", "account_number"]

    def __str__(self):
        return f"{self.nickname or self.account_name} - {self.account_number}"


# ======================
# 💰 PAYMENT REQUEST MODEL
# ======================
class PaymentRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_requests")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_requests")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paystack_request_code = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Payment Request"
        verbose_name_plural = "Payment Requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Request ₦{self.amount} from {self.requester} to {self.recipient}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)


# ======================
# ⚡ SIGNALS
# ======================
@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """Automatically create a wallet for every new user."""
    if created and not hasattr(instance, "wallet"):
        Wallet.objects.create(user=instance)
