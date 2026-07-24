# Generated manually to add Settings > Verification support

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0053_profile_privacy_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='phone_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='IDVerification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document', models.FileField(blank=True, null=True, upload_to='verification/id_documents/')),
                ('status', models.CharField(
                    choices=[
                        ('not_submitted', 'Not Submitted'),
                        ('pending', 'Pending Review'),
                        ('verified', 'Verified'),
                        ('rejected', 'Rejected'),
                    ],
                    default='not_submitted',
                    max_length=13,
                )),
                ('rejection_reason', models.CharField(blank=True, max_length=255)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='id_verification',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]