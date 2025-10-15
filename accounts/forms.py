from django import forms
from django.contrib.auth.models import User
from .models import Profile  # assuming you have a Profile model linked to User
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "w-full border border-border rounded-lg px-3 py-2"}),
            "last_name": forms.TextInput(attrs={"class": "w-full border border-border rounded-lg px-3 py-2"}),
            "email": forms.EmailInput(attrs={"class": "w-full border border-border rounded-lg px-3 py-2"}),
        }

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "phone",
            "avatar",
            "bank_name",
            "account_number",
            "account_name",
        ]
        widgets = {
            "phone": forms.TextInput(attrs={"class": "w-full border border-border rounded-lg px-3 py-2"}),
            "bank_name": forms.TextInput(attrs={"class": "w-full border border-border rounded-lg px-3 py-2"}),
            "account_number": forms.TextInput(attrs={"class": "w-full border border-border rounded-lg px-3 py-2"}),
            "account_name": forms.TextInput(attrs={"class": "w-full border border-border rounded-lg px-3 py-2"}),
        }


class StyledPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:outline-none",
            "placeholder": "Enter your current password"
        })
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:outline-none",
            "placeholder": "Enter a new password"
        })
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:outline-none",
            "placeholder": "Confirm new password"
        })
    )

class StyledSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:outline-none",
            "placeholder": "Enter a new password"
        })
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary focus:outline-none",
            "placeholder": "Confirm new password"
        })
    )