# Generated manually to add HomeFinder KE Settings fields to Profile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_profile_account_type_alter_residencephoto_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='cover_photo',
            field=models.ImageField(upload_to='profiles/covers/', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='county',
            field=models.CharField(
                max_length=100,
                blank=True,
                choices=[
                    ('Nairobi', 'Nairobi'),
                    ('Kiambu', 'Kiambu'),
                    ('Machakos', 'Machakos'),
                    ('Kajiado', 'Kajiado'),
                    ('Muranga', "Murang'a"),
                    ('Nakuru', 'Nakuru'),
                    ('Mombasa', 'Mombasa'),
                    ('Kisumu', 'Kisumu'),
                    ('Uasin Gishu', 'Uasin Gishu'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='profile',
            name='town',
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='language',
            field=models.CharField(
                max_length=5,
                choices=[('en', 'English'), ('sw', 'Kiswahili')],
                default='en',
            ),
        ),
    ]