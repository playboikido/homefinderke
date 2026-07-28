import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0004_expand_categories'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BusinessCoupon',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=30)),
                ('discount_type', models.CharField(choices=[('percent', 'Percentage Off'), ('fixed', 'Fixed Amount Off')], default='percent', max_length=10)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=8)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('max_uses', models.PositiveIntegerField(blank=True, help_text='Blank = unlimited uses', null=True)),
                ('times_used', models.PositiveIntegerField(default=0)),
                ('valid_from', models.DateField()),
                ('valid_until', models.DateField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupons', to='business.business')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='BusinessPromotion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('placement', models.CharField(choices=[('category_featured', 'Featured in Category Page'), ('homepage', 'Homepage Featured'), ('residence_pages', 'Featured on Residence Pages')], default='category_featured', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('active', 'Active'), ('ended', 'Ended'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('starts_on', models.DateField()),
                ('ends_on', models.DateField()),
                ('admin_notes', models.CharField(blank=True, help_text='Internal notes, not shown to the business', max_length=300)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='promotions', to='business.business')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='businesscoupon',
            constraint=models.UniqueConstraint(fields=('business', 'code'), name='unique_business_coupon_code'),
        ),
    ]