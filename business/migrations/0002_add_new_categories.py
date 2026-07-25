from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='business',
            name='category',
            field=models.CharField(
                choices=[
                    ('movers', 'Movers'),
                    ('furniture', 'Furniture Store'),
                    ('curtains', 'Curtains & Blinds'),
                    ('electronics', 'Electronics & Appliances'),
                    ('kitchen', 'Kitchen & Home Fittings'),
                    ('mattresses', 'Mattresses & Bedding'),
                    ('bathroom', 'Bathroom & Sanitary'),
                    ('cleaning', 'Cleaning Services'),
                    ('lighting', 'Lighting'),
                    ('repairs', 'Repairs & Maintenance'),
                    ('garden', 'Garden & Landscaping'),
                    ('internet', 'Internet Providers'),
                    ('security', 'Security Companies'),
                    ('househelp', 'Househelp & Domestic Staff'),
                    ('carpets', 'Carpets & Rugs'),
                    ('bedding', 'Duvets & Blankets'),
                    ('other', 'Other'),
                ],
                default='other',
                max_length=20,
            ),
        ),
    ]