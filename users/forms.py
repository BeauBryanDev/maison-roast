from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form"""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-amber-700 transition duration-300 bg-amber-50',
            'placeholder': 'Enter your email address'
        })
    )

    first_name = forms.CharField(
        max_length=32,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-amber-700 transition duration-300 bg-amber-50',
            'placeholder': 'Enter your first name'
        })
    )

    last_name = forms.CharField(
        max_length=32,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-amber-700 transition duration-300 bg-amber-50',
            'placeholder': 'Enter your last name'
        })
    )

    phone_number = forms.CharField(
        max_length=16,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-amber-700 transition duration-300 bg-amber-50',
            'placeholder': 'Enter your phone number'
        })
    )

    address = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-amber-700 transition duration-300 bg-amber-50',
            'placeholder': 'Enter your address',
            'rows': 3
        })
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'address', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-amber-700 transition duration-300 bg-amber-50',
                'placeholder': 'Choose a username'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-amber-700 transition duration-300 bg-amber-50',
            'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:border-amber-700 transition duration-300 bg-amber-50',
            'placeholder': 'Confirm your password'
        })

    def save(self, commit=True):
        
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.phone_number = self.cleaned_data.get('phone_number', '')
        user.address = self.cleaned_data.get('address', '')
        
        if commit:
            user.save()
            
        return user
