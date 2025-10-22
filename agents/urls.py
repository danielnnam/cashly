from django.urls import path
from . import views

app_name = "agents"

urlpatterns = [
    path("dashboard/", views.agent_dashboard, name="dashboard"),
    path("become-agent/", views.become_agent, name="become_agent"),
    path("agent_wallet/", views.agent_wallet, name="agent_wallet"),
    path('history/', views.agent_history, name='agent_history'),
    path('suspended/', views.suspension_notice, name='suspension_notice'),
    path('appeal-suspension/', views.appeal_suspension, name='appeal_suspension'),
    path('logout/', views.logout_view, name='logout'), 
]
