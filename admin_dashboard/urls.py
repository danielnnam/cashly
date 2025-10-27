from django.urls import path
from . import views

app_name = "admin_dashboard"

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('chart-data/', views.transaction_chart_data, name='transaction_chart_data'),
    path("activity-data/", views.recent_activity, name="recent_activity"),
    path('users/', views.users_list, name='users'),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path('user/<int:user_id>/suspend/', views.suspend_user, name='admin_suspend_user'),
    path('user/<int:user_id>/delete/', views.delete_user, name='admin_delete_user'),
    path("agents/", views.admin_agents_list, name="agents"),
    path("agents/<str:reference>/", views.admin_agent_detail, name="admin_agent_detail"),
    path('agents/<str:reference>/approve/', views.approve_agent, name='approve_agent'),
    path('agents/<str:reference>/decline/', views.decline_agent, name='decline_agent'),
    path('agents/<str:reference>/suspend/', views.suspend_agent, name='suspend_agent'),
    path('agents/<str:reference>/unsuspend/', views.unsuspend_agent, name='unsuspend_agent'),
    path('agents/<str:reference>/delete/', views.delete_agent, name='delete_agent'),
    path("agent/<str:reference>/appeal/accept/", views.accept_appeal, name="accept_appeal"),
    path("agent/<str:reference>/appeal/reject/", views.reject_appeal, name="reject_appeal"),
    path("notifications/", views.admin_notifications_page, name="admin_notifications"),
    path("notifications/read/<int:notif_id>/", views.mark_admin_notification_as_read, name="mark_admin_notification_as_read"),
    path("transactions/", views.transactions_list, name="transactions"),
    path("disputes/", views.disputes_list, name="admin_disputes_list"),
    path("disputes/<int:pk>/", views.dispute_detail, name="admin_dispute_detail"),
    path('disputes/<int:dispute_id>/resolve/', views.resolve_dispute, name='resolve_dispute'),
]