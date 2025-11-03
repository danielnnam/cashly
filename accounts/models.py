from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
# Create your models here.


def user_avatar_path(instance, filename):
    # upload avatars to: media/avatars/user_<id>/<filename>
    return f"avatars/user_{instance.user.id}/{filename}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True, null=True)
    avatar = models.ImageField(upload_to=user_avatar_path, blank=True, null=True)
    is_agent = models.BooleanField(default=False)   # ✅ added this field
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True, null=True)
    agent_response = models.TextField(blank=True, null=True)
    suspension_appeal = models.TextField(blank=True, null=True)

    # Admin-specific settings
    dark_mode = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    default_landing_page = models.CharField(max_length=50, default='dashboard')  
    appeal_status = models.CharField(
        max_length=20,
        choices=[
            ("none", "No Appeal"),
            ("pending", "Pending Review"),
            ("resolved", "Resolved"),
        ],
        default="none"
    )

    # Payment details for deposits
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=20, blank=True, null=True)
    account_name = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self):
        return self.user.username

class LoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    session_key = models.CharField(max_length=40, db_index=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        # delete old duplicates before saving
        LoginActivity.objects.filter(
            user=self.user,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            session_key=self.session_key,
        ).exclude(pk=self.pk).delete()

        super().save(*args, **kwargs)




class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="user_notifications",
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"



