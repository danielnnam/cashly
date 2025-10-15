"""
URL configuration for simplebank_project project.
"""

from django.contrib import admin
from django.urls import path, include
from accounts import views  
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # ✅ Allauth URLs MUST come before your custom auth URLs
    path('accounts/', include('allauth.urls')),
    
    # Your custom auth routes - under different path to avoid conflicts
    path('auth/', include('accounts.urls')), 
    
    # Home page
    path('', views.home, name='home'),
    
    # Other apps
    path('wallet/', include('wallet.urls')),
    path('payments/', include('payments.urls')),
    path("agents/", include("agents.urls", namespace="agents")),
    path('admin-dashboard/', include('admin_dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)