from django.contrib import admin
from django.shortcuts import redirect

# Override admin homepage
admin.site.index_template = None

def custom_admin_index(request):
    return redirect("admin_dashboard")

admin.site.index = custom_admin_index
