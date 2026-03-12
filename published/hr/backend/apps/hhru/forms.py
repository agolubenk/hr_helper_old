from django import forms
from .models import HHruOAuthConfig


class HHruOAuthConfigForm(forms.ModelForm):
    class Meta:
        model = HHruOAuthConfig
        fields = ('name', 'client_id', 'client_secret', 'redirect_uri', 'is_active', 'is_default')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'client_id': forms.TextInput(attrs={'class': 'form-control'}),
            'client_secret': forms.TextInput(attrs={'class': 'form-control', 'type': 'password'}),
            'redirect_uri': forms.URLInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
