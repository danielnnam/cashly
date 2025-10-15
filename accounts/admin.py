from django.contrib import admin
from .models import Profile, LoginActivity, Notification
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "is_agent")
    search_fields = ("user__username", "user__email", "phone")
    list_filter = ("is_agent",)

    
admin.site.register(LoginActivity)
admin.site.register(Notification)