# Fields already added in 0051_profile_compact_mode_profile_hide_email_and_more
# This migration is kept as a no-op to preserve the dependency chain.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_profile_appearance_fields'),
    ]

    operations = []