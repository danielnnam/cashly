from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User
from django.contrib import messages

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    
    def populate_user(self, request, sociallogin, data):
        """Ensure email and name are properly saved from Google"""
        user = super().populate_user(request, sociallogin, data)
        
        # Extract data from Google
        extra_data = sociallogin.account.extra_data
        
        # Ensure email is set
        if extra_data.get('email') and not user.email:
            user.email = extra_data.get('email')
        
        # Set first and last name from Google
        if extra_data.get('given_name') and not user.first_name:
            user.first_name = extra_data.get('given_name', '')
        
        if extra_data.get('family_name') and not user.last_name:
            user.last_name = extra_data.get('family_name', '')
            
        return user
    
    def save_user(self, request, sociallogin, form=None):
        """Save user with Google data"""
        user = super().save_user(request, sociallogin, form)
        
        # Debug print
        print(f"Google user created: {user.email} - {user.first_name} {user.last_name}")
        
        return user