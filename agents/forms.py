from django import forms
from .models import AgentApplication

class AgentApplicationForm(forms.ModelForm):
    class Meta:
        model = AgentApplication
        fields = [  "account_number", "bank_name", "phone", "location", "reason"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                "class": "w-full px-4 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm",
                "placeholder": field.label
            })