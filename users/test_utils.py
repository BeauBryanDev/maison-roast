
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

ADULT_DOB = date(1990, 1, 1)

# Test helpers for users.

# gender and date_of_birth are NOT NULL with no default, so every test that makes
# a user must supply them. These wrap that up.

def minor_dob():
    """A DOB one day short of the legal age."""
    return User.legal_age_cutoff() + timedelta(days=1)


def adult_dob():
    """A DOB exactly on the legal age."""
    return User.legal_age_cutoff()


def make_user(username='testuser', email=None, password='testpassword123',
              gender=User.Gender.MALE, date_of_birth=ADULT_DOB, **kwargs):
    
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com' if email is None else email,
        password=password,
        gender=gender,
        date_of_birth=date_of_birth,
        **kwargs
    )


def make_minor(username='minor', **kwargs):
    
    return make_user(username=username, date_of_birth=minor_dob(), **kwargs)
