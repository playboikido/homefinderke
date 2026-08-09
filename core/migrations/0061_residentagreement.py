import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0060_idverification_verification_documents'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResidentAgreement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('terms_version', models.CharField(max_length=20)),
                ('terms_snapshot', models.TextField(help_text='Full terms text as it existed at the moment of consent')),
                ('agreed_at', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='resident_agreements',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-agreed_at'],
            },
        ),
    ]