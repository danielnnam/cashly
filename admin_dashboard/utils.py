from django.contrib.auth import get_user_model
from admin_dashboard.models import ActivityLog, AdminNotification

User = get_user_model()


def log_activity(
    user=None,
    title="",
    description="",
    type="transaction",
    status="pending",
    icon="exchange-alt"
):

    try:
        # ✅ 1. Create an activity record
        activity = ActivityLog.objects.create(
            user=user if user and hasattr(user, "is_authenticated") else None,
            title=title,
            description=description,
            type=type,
            status=status,
            icon=icon,
        )

        # ✅ 2. Notify all admin/staff users
        admins = User.objects.filter(is_staff=True)
        for admin in admins:
            AdminNotification.objects.create(
                admin_user=admin,
                title=title,
                message=description,
            )

        return activity

    except Exception as e:
        # Prevent any crash
        print(f"[ActivityLog Error] Could not log activity: {e}")
        return None
