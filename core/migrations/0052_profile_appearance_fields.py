# Generated manually to add Settings > Appearance fields to Profile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_profile_compact_mode_profile_hide_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='theme_preference',
            field=models.CharField(
                max_length=6,
                choices=[('system', 'System'), ('light', 'Light'), ('dark', 'Dark')],
                default='system',
            ),
        ),
        migrations.AddField(
            model_name='profile',
            name='reduce_motion',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='profile',
            name='compact_mode',
            field=models.BooleanField(default=False),
        ),
    ]
