# Generated manually to add Settings > Privacy fields to Profile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_profile_appearance_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='profile_visibility',
            field=models.CharField(
                max_length=7,
                choices=[('public', 'Public'), ('private', 'Private')],
                default='public',
            ),
        ),
        migrations.AddField(
            model_name='profile',
            name='hide_phone',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='profile',
            name='hide_email',
            field=models.BooleanField(default=True),
        ),
    ]