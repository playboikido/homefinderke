import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0005_coupons_promotions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BusinessService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('category', models.CharField(blank=True, max_length=100)),
                ('price', models.DecimalField(blank=True, decimal_places=2, help_text='Starting price, if applicable', max_digits=10, null=True)),
                ('duration_minutes', models.PositiveIntegerField(blank=True, help_text='Typical time to complete, if relevant', null=True)),
                ('description', models.TextField(blank=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='business/services/')),
                ('is_available', models.BooleanField(default=True)),
                ('views_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='services', to='business.business')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='BusinessBooking',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('customer_name', models.CharField(max_length=150)),
                ('customer_phone', models.CharField(blank=True, max_length=20)),
                ('customer_email', models.EmailField(blank=True, max_length=254)),
                ('requested_date', models.DateField()),
                ('requested_time', models.TimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending Confirmation'), ('confirmed', 'Confirmed'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='pending', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='business.business')),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('service', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='business.businessservice')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='businessservice',
            index=models.Index(fields=['business', 'is_available'], name='business_bs_bus_avail_idx'),
        ),
    ]