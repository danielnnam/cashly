"""
URL configuration for simplebank_project project.
"""

from django.contrib import admin
from django.urls import path, include
from accounts import views  
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import re_path
from django.conf.urls import handler400, handler403, handler404, handler500


urlpatterns = [
    # path('admin/', admin.site.urls),
    
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

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# ✅ Serve static & media files safely even when DEBUG=False (for local or testing)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]

handler400 = "accounts.views.bad_request_view"
handler403 = "accounts.views.permission_denied_view"
handler404 = "accounts.views.page_not_found_view"
handler500 = "accounts.views.server_error_view"