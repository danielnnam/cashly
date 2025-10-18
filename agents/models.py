from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

User = settings.AUTH_USER_MODEL

# Create your models here.

class AgentApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_applications")
    phone = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=150)
    account_number = models.CharField(max_length=20)
    location = models.CharField(max_length=100)
    reason = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    decline_reason = models.TextField(blank=True, null=True)

    # ✅ New field for professional reference ID
    reference = models.CharField(max_length=30, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.reference:
            # Example: AGT_A92F7E3C_20251018
            date_str = timezone.now().strftime("%Y%m%d")
            unique_id = uuid.uuid4().hex[:8].upper()
            self.reference = f"AGT_{unique_id}_{date_str}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} ({self.reference}) - {self.status}"
    