# accounts/utils.py
from admin_dashboard.models import ActivityLog

def log_activity(
    user=None,
    title="",
    description="",
    type="system",
    status="pending",
    icon="info-circle"
):
    """
    Create an activity log entry for admin dashboard tracking.
    Used for deposits, withdrawals, disputes, agent applications, etc.
    """
    try:
        ActivityLog.objects.create(
            user=user,
            title=title,
            description=description,
            type=type,
            status=status,
            icon=icon,
        )
    except Exception as e:
        # Avoid crashing the transaction flow just because of a log error
        print(f"[ActivityLog Error]: {e}")
