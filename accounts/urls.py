from django.urls import path
from . import views

urlpatterns = [
    # Remove the custom Google callback - Allauth handles this automatically
    # path('google/callback/', views.google_callback, name='google_callback'),
    
    # Your custom auth routes
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),  # ✅ Uncomment this
    path('dashboard/', views.dashboard, name='dashboard'),
    path("settings/", views.settings_view, name="settings"),
    path("settings/edit-profile/", views.edit_profile, name="edit_profile"),
    path("settings/change-password/", views.change_password, name="change_password"),
    path("settings/login-activity/", views.login_activity, name="login_activity"),
    path("login-activity/logout-sessions/", views.logout_sessions, name="logout_sessions"),
    path("notifications/", views.notifications_list, name="notifications_list"),
    # path("notifications/<int:notification_id>/", views.notification_detail, name="notification_detail"),
    path("notifications/mark-as-read/<int:pk>/", views.mark_notification_as_read, name="mark_notification_as_read"),
    path("switch-to-user/", views.switch_to_user, name="switch_to_user"),
    path("switch-to-agent/", views.switch_to_agent, name="switch_to_agent"),

]