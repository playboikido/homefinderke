import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0008_business_ai_usage'),
    ]

    operations = [
        migrations.CreateModel(
            name='BusinessBranch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="e.g. 'Westlands Branch'", max_length=150)),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('whatsapp_number', models.CharField(blank=True, max_length=20)),
                ('county', models.CharField(blank=True, max_length=100)),
                ('town', models.CharField(blank=True, max_length=100)),
                ('estate', models.CharField(blank=True, max_length=100)),
                ('street', models.CharField(blank=True, max_length=200)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('opens_at', models.TimeField(blank=True, null=True)),
                ('closes_at', models.TimeField(blank=True, null=True)),
                ('closed_weekdays', models.CharField(blank=True, help_text='Comma-separated, 0=Mon..6=Sun', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branches', to='business.business')),
            ],
            options={'ordering': ['name']},
        ),
    ]