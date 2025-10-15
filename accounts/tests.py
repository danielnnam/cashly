from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils.timezone import now

from .utils import create_notification

User = get_user_model()

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    create_notification(user, "Login Successful", f"You logged in at {now().strftime('%Y-%m-%d %H:%M:%S')}")

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        create_notification(user, "Logout", f"You logged out at {now().strftime('%Y-%m-%d %H:%M:%S')}")

@receiver(post_save, sender=User)
def user_profile_update(sender, instance, created, **kwargs):
    if not created:
        create_notification(instance, "Profile Updated", "Your account information was updated successfully.")
