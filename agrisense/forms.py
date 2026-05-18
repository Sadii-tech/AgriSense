from django import forms
from .models import SiteBranding
from django.contrib.auth.forms import SetPasswordForm
class BrandingForm(forms.ModelForm):
    class Meta:
        model = SiteBranding
        fields = ['app_name', 'app_subtitle']
        widgets = {
            'app_name': forms.TextInput(attrs={
                'class': 'settings-input flex-1',
                'placeholder': 'Enter app name',
            }),
            'app_subtitle': forms.TextInput(attrs={
                'class': 'settings-input flex-1',
                'placeholder': 'Enter subtitle',
            }),
        }
        
# forms.py
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        


class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="New Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "class": "form-control",
            "placeholder": "Enter new password"
        }),
    )
    new_password2 = forms.CharField(
        label="Confirm Password",  # ✅ Custom label
        strip=False,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "class": "form-control",
            "placeholder": "Confirm new password"
        }),
    )
    
class CustomPasswordResetForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
