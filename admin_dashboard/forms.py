from django import forms
from accounts.models import Profile

class AdminSettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'phone', 'bank_name', 'account_name', 'account_number']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'input-field'}),
            'bank_name': forms.TextInput(attrs={'class': 'input-field'}),
            'account_name': forms.TextInput(attrs={'class': 'input-field'}),
            'account_number': forms.TextInput(attrs={'class': 'input-field'}),
        }
