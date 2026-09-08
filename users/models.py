from datetime import date

from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


# Create your models here.
class CustomUser(AbstractUser):
    """Custom User model extending AbstractUser"""

    class Gender(models.TextChoices):
        MALE = 'MALE', _('Male')
        FEMALE = 'FEMALE', _('Female')
        OTHER = 'OTHER', _('Other')

    username = models.CharField(_('username'), max_length=128, unique=True)
    first_name = models.CharField(_('first name'), max_length=32, blank=True)
    last_name = models.CharField(_('last name'), max_length=32, blank=True)
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(_('phone number'), max_length=16, blank=True, null=True)
    address = models.CharField(_('address'), max_length=255, blank=True)

    # Mandatory at sign-up, never editable: the alcohol age gate depends on them.
    gender = models.CharField(_('gender'), max_length=16, choices=Gender.choices)
    date_of_birth = models.DateField(_('date of birth'), db_index=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_groups',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )
    
    @property
    def age(self):
        """Whole years since date_of_birth, or None. Computed, never stored --
        a STORED generated column needs an immutable expression, and
        CURRENT_DATE is not one."""
        dob = self.date_of_birth
        if dob is None:
            return None
        today = date.today()
        # Drop a year if this year's birthday has not happened yet.
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def is_of_legal_age(self):
        """Old enough to buy alcohol. An unknown DOB never is."""
        age = self.age
        return age is not None and age >= settings.MINIMUM_ALCOHOL_AGE

    @classmethod
    def legal_age_cutoff(cls):
        """Latest DOB still of legal age today; for `date_of_birth__gt=` queries."""
        today = date.today()
        try:
            return today.replace(year=today.year - settings.MINIMUM_ALCOHOL_AGE)
        except ValueError:
            # 29 Feb landing in a non-leap year.
            return today.replace(year=today.year - settings.MINIMUM_ALCOHOL_AGE, day=28)

    def __str__(self):

        return f"{self.username} - {self.email} - {self.first_name} {self.last_name}"