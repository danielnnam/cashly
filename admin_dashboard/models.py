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
