from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    # -------------------------
    # USER — Deposits (P2P escrow)
    # -------------------------
    path("deposit/start/", views.start_deposit, name="start_deposit"),
    path("deposit/agents/", views.choose_agent, name="choose_agent"),
    path("deposit/create/", views.create_deposit, name="create_deposit"),
    path("deposit/<str:reference>/", views.user_deposit_detail, name="user_deposit_detail"),
    path("deposit/<str:reference>/upload-receipt/", views.upload_receipt, name="upload_receipt"),
    path("requests/", views.users_request_list, name="users_request_list"),
    path("requests/<str:reference>/", views.user_request_detail, name="user_request_detail"),


    # -------------------------
    # USER — Withdrawals (P2P escrow)
    # -------------------------
    path("withdraw/start/", views.start_withdrawal, name="start_withdrawal"),
    path("withdraw/choose-agent/", views.choose_agent_withdrawal, name="choose_agent_withdrawal"),
    path("withdraw/create/", views.create_withdrawal, name="create_withdrawal"),
    path("withdraw/<str:reference>/", views.withdrawal_detail, name="withdrawal_detail"),
    path("withdraw/<str:reference>/confirm/", views.user_confirm_withdrawal, name="user_confirm_withdrawal"),

    # -------------------------
    # SHARED — Mark or Upload Actions
    # -------------------------
    path("requests/<str:reference>/mark-as-paid/", views.mark_as_paid_request, name="mark_as_paid_request"),

    # -------------------------
    # AGENT — P2P Dashboard
    # -------------------------
    path("agent/requests/", views.agent_request_list, name="agent_request_list"),
    path("agent/requests/<str:reference>/", views.agent_request_detail, name="agent_request_detail"),
    path("agent/requests/<str:reference>/take/", views.agent_take_request, name="agent_take_request"),
    path("agent/request/<str:reference>/confirm/", views.agent_confirm_request, name="agent_confirm_request"),
    path("agent/withdraw/<str:reference>/paid/", views.agent_mark_withdrawal_paid, name="agent_mark_withdrawal_paid"),
]




















# from django.urls import path
# from . import views

# app_name = 'payments'
# urlpatterns = [
#     path("deposit/start/", views.start_deposit, name="start_deposit"),
#     path("deposit/agents/", views.choose_agent, name="choose_agent"),
#     path("deposit/create/", views.create_deposit, name="create_deposit"),
#     # path("deposit/<str:reference>/", views.deposit_detail, name="deposit_detail"),
#     path("upload-receipt/<str:reference>/", views.upload_receipt, name="upload_receipt"),  


#     # -------------------------
#     # User-facing (My requests)
#     # -------------------------
#     path("requests/", views.users_request_list, name="users_request_list"),
#     path("requests/<str:reference>/", views.user_request_detail, name="user_request_detail"),
#     path("deposits/<str:reference>/", views.user_deposit_detail, name="user_deposit_detail"),
#     path("requests/<str:reference>/mark-as-paid/", views.mark_as_paid_request, name="mark_as_paid_request"),
#     path("requests/<str:reference>/cancel/", views.user_cancel_request, name="user_cancel_request"),

#     # -------------------------
#     # Agent-facing (prefixed to avoid clashes)
#     # -------------------------
#     path("agent/requests/", views.agent_request_list, name="agent_request_list"),
#     path("agent/requests/<str:reference>/", views.agent_request_detail, name="agent_request_detail"),
#     path("agent/requests/<str:reference>/take/", views.agent_take_request, name="agent_take_request"),
#     path("agent/requests/<str:reference>/confirm/", views.agent_confirm_request, name="agent_confirm_request"),
#     path("agent/requests/<str:reference>/reject/", views.agent_reject_request, name="agent_reject_request"),

#     # -------------------------
#     # User-withdrawals (My requests)
#     # -------------------------
#     path('withdraw/start/', views.start_withdrawal, name='start_withdrawal'),
#     path('withdraw/choose-agent/', views.choose_agent_withdrawal, name='choose_agent_withdrawal'),
#     path('withdraw/create/', views.create_withdrawal, name='create_withdrawal'),
#     path('withdraw/<str:reference>/confirm/', views.user_confirm_withdrawal, name='user_confirm_withdrawal'),
#     path('agent/<str:reference>/paid/', views.agent_mark_as_paid, name='agent_mark_as_paid'),
#     path("withdraw/<str:reference>/", views.withdrawal_detail, name="withdrawal_detail"),

# ]
