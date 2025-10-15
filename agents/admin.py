from django.contrib import admin
from .models import AgentApplication
from accounts.models import Profile

# Register your models here.

@admin.register(AgentApplication)
class AgentApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "created_at")
    actions = ["approve_applications", "reject_applications"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # ✅ Sync profile automatically
        profile, created = Profile.objects.get_or_create(user=obj.user)
        if obj.status == "approved":
            profile.is_agent = True
            # Copy bank details
            profile.bank_name = obj.bank_name
            profile.account_name = obj.account_name
            profile.account_number = obj.account_number
        else:
            profile.is_agent = False
        profile.save()

    @admin.action(description="Approve selected applications")
    def approve_applications(self, request, queryset):
        for app in queryset:
            app.status = "approved"
            app.save()

            profile, created = Profile.objects.get_or_create(user=app.user)
            profile.is_agent = True
            # Copy bank details
            profile.bank_name = app.bank_name
            profile.account_name = app.account_name
            profile.account_number = app.account_number
            profile.save()

        self.message_user(request, "Selected applications approved and bank details synced.")

    @admin.action(description="Reject selected applications")
    def reject_applications(self, request, queryset):
        for app in queryset:
            app.status = "rejected"
            app.save()
            profile, created = Profile.objects.get_or_create(user=app.user)
            profile.is_agent = False
            profile.save()

        self.message_user(request, "Selected applications rejected.")


