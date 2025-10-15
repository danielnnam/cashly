from django.shortcuts import render

# Create your views here.

def admin_dashboard(request):
    return render(request, 'admin_dashboard/dashboard.html')

def admin_login(request):
    return render(request, 'admin_dashboard/login.html')