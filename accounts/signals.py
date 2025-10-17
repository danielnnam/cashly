from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Notification, Profile
from .models import LoginActivity
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in
from admin_dashboard.utils import log_activity

@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=Profile)
def profile_updated_notification(sender, instance, created, **kwargs):
    if not created:  # only for updates
        Notification.objects.create(
            user=instance.user,
            title="Profile Updated",
            message="Your profile information has been updated successfully."
        )

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    ip = get_client_ip(request)

    LoginActivity.objects.create(
        user=user,
        ip_address=ip,
        user_agent=user_agent,
        timestamp=timezone.now()
    )


def get_client_ip(request):
    """Get real IP even behind proxies"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")



@receiver(post_save, sender=User)
def new_user_registered(sender, instance, created, **kwargs):
    """Logs new user registrations to admin activity dashboard."""
    if created:
        # You can detect if it’s a Google user via allauth if needed
        login_method = "Google" if instance.socialaccount_set.exists() else "Email"

        log_activity(
            user=instance,
            title="New User Registration",
            description=f"User #{instance.id} ({instance.username}) registered via {login_method}",
            type="user_registration",
            status="completed",
            icon="user-plus"
        )
