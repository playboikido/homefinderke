from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0059_resident_onboarding_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='idverification',
            name='kra_pin_document',
            field=models.FileField(
                blank=True, null=True, upload_to='verification/kra_pin/',
                help_text='Required for landlords and agents.',
            ),
        ),
        migrations.AddField(
            model_name='idverification',
            name='property_proof_document',
            field=models.FileField(
                blank=True, null=True, upload_to='verification/property_proof/',
                help_text='Agents only: proof of the rental properties/homes you manage or represent.',
            ),
        ),
    ]