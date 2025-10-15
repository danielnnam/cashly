from django.db import models
from django.conf import settings

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

    def __str__(self):
        return f"Application from {self.user.username} - {self.status}"

    