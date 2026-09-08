from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

MAX_AGE = 120


class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form"""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'field-cream',
            'placeholder': 'Enter your email address'
        })
    )

    first_name = forms.CharField(
        max_length=32,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'field-cream',
            'placeholder': 'Enter your first name'
        })
    )

    last_name = forms.CharField(
        max_length=32,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'field-cream',
            'placeholder': 'Enter your last name'
        })
    )

    phone_number = forms.CharField(
        max_length=16,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'field-cream',
            'placeholder': 'Enter your phone number'
        })
    )

    address = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'field-cream',
            'placeholder': 'Enter your address',
            'rows': 3
        })
    )

    gender = forms.ChoiceField(
        choices=CustomUser.Gender.choices,
        required=True,
        widget=forms.RadioSelect,
    )

    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'field-cream',
            'max': date.today().isoformat(),
        }),
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number',
                  'address', 'gender', 'date_of_birth', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'field-cream',
                'placeholder': 'Choose a username'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'field-cream',
            'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'field-cream',
            'placeholder': 'Confirm your password'
        })

    def clean_date_of_birth(self):
        """The browser's `max` is a hint; this is the check that counts."""
        dob = self.cleaned_data['date_of_birth']
        today = date.today()
        if dob > today:
            raise forms.ValidationError('Date of birth cannot be in the future.')
        if dob.year < today.year - MAX_AGE:
            raise forms.ValidationError('Please enter a valid date of birth.')
        return dob

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
