from django.db import migrations, models


def mark_existing_profiles_onboarded(apps, schema_editor):
    """
    Resident onboarding is new. Existing users already use the app day to
    day — they must NOT be forced through the wizard retroactively on their
    next request. Only profiles created after this migration should start
    at step 1 / incomplete.
    """
    Profile = apps.get_model('core', 'Profile')
    Profile.objects.update(onboarding_complete=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0058_alter_incident_category_alter_residencephoto_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='resident_role',
            field=models.CharField(
                blank=True,
                choices=[('normal', 'Normal / Renter'), ('landlord', 'Landlord'), ('agent', 'Agent')],
                help_text='Only meaningful when account_type is resident.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='profile',
            name='onboarding_step',
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='profile',
            name='onboarding_complete',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_profiles_onboarded, noop_reverse),
    ]