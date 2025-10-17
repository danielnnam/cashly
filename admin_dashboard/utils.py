from admin_dashboard.models import ActivityLog

def log_activity(
    user=None,
    title="",
    description="",
    type="transaction",
    status="pending",
    icon="exchange-alt"
):
    """
    Log any significant event in the system for the admin dashboard.

    Args:
        user: The user related to the event (can be None for system events)
        title: Short summary of the activity (e.g. "Deposit Request Created")
        description: Detailed context about the action
        type: One of ActivityLog.ACTIVITY_TYPES
        status: One of ActivityLog.STATUS_CHOICES
        icon: FontAwesome icon name (without 'fa-' prefix)
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
        # Prevent this from breaking the main flow
        print(f"[ActivityLog Error] Could not log activity: {e}")
