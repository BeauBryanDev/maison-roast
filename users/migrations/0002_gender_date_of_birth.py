"""Add gender and date_of_birth to CustomUser, both NOT NULL.

Nullable -> backfill -> NOT NULL: a NOT NULL column cannot be added to a
populated table. No model-level default, or sign-up could omit the fields.
"""

import datetime

from django.db import migrations, models

BACKFILL_GENDER = 'MALE'
BACKFILL_DOB = datetime.date(2005, 8, 22)


def backfill(apps, schema_editor):
    CustomUser = apps.get_model('users', 'CustomUser')
    CustomUser.objects.filter(gender__isnull=True).update(gender=BACKFILL_GENDER)
    CustomUser.objects.filter(date_of_birth__isnull=True).update(date_of_birth=BACKFILL_DOB)


def unbackfill(apps, schema_editor):
    """Nothing to undo; reversing AddField drops the columns."""


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='gender',
            field=models.CharField(
                choices=[('MALE', 'Male'), ('FEMALE', 'Female'), ('OTHER', 'Other')],
                max_length=16,
                null=True,
                verbose_name='gender',
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='date_of_birth',
            field=models.DateField(db_index=True, null=True, verbose_name='date of birth'),
        ),
        migrations.RunPython(backfill, unbackfill),
        migrations.AlterField(
            model_name='customuser',
            name='gender',
            field=models.CharField(
                choices=[('MALE', 'Male'), ('FEMALE', 'Female'), ('OTHER', 'Other')],
                max_length=16,
                verbose_name='gender',
            ),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='date_of_birth',
            field=models.DateField(db_index=True, verbose_name='date of birth'),
        ),
    ]
