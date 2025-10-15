# payments/forms.py
from django import forms
from .models import DepositRequest
from accounts.models import Profile
from .models import DepositRequest


class DepositAmountForm(forms.Form):
    amount = forms.DecimalField(
        min_value=100,
        max_value=1000000,
        decimal_places=2,
        label="Deposit Amount",
        widget=forms.NumberInput(attrs={
            "class": "w-full px-4 py-3 border border-border rounded-lg",
            "placeholder": "Enter amount (e.g. 5000)"
        })
    )

class ReceiptUploadForm(forms.ModelForm):
    class Meta:
        model = DepositRequest
        fields = ["receipt"]



class WithdrawalAmountForm(forms.Form):
    amount = forms.DecimalField(
        min_value=100,
        max_value=1000000,
        decimal_places=2,
        label="Amount (₦)",
        widget=forms.NumberInput(attrs={
            "class": "w-full px-4 py-3 border border-border rounded-lg text-sm font-medium mb-2",
            "placeholder": "Enter amount (e.g. 5000)"
        })
    )

class WithdrawalReceiptForm(forms.ModelForm):
    class Meta:
        from .models import WithdrawalRequest
        model = WithdrawalRequest
        fields = ["receipt"]
