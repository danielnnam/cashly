# admin_dashboard/context_processors.py
from .models import AdminNotification

def admin_notifications_context(request):
    if request.user.is_authenticated and request.user.is_staff:
        unread_count = request.user.admin_notifications.filter(is_read=False).count()
        recent_notifications = request.user.admin_notifications.all()[:5]
        return {
            'admin_unread_count': unread_count,
            'admin_recent_notifications': recent_notifications,
        }
    return {}
