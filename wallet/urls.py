from django.urls import path
from . import views

app_name = 'wallet'  # Namespace for multi-app routing
urlpatterns = [
    # path('balance/', views.wallet_balance, name='wallet_balance'),
    path('api/balance/', views.get_balance_api, name='get_balance_api'),
    path("get-balance/", views.get_balance_api, name="get_balance_api"),
    path("overview/", views.wallet_overview, name="overview"),
    path("send/", views.send_money, name="send"),
    path("lookup-account/", views.lookup_account, name="lookup_account"),
    path("history/", views.transaction_history, name="history"),
    path("history/<str:transaction_id>/", views.transaction_detail, name="transaction_detail"),
]
