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
    
]