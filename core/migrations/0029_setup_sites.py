from django.db import migrations

def setup_default_site(apps, schema_editor):
    try:
        Site = apps.get_model('sites', 'Site')
        
        # Configure Site 1 (default) for local dev/fallback if it exists
        site1 = Site.objects.filter(id=1).first()
        if site1:
            site1.domain = '127.0.0.1:8000'
            site1.name = 'HomeFinderKE Local'
            site1.save()
        else:
            Site.objects.get_or_create(id=1, defaults={'domain': '127.0.0.1:8000', 'name': 'HomeFinderKE Local'})

        # Configure Site 3 for production if it exists
        site3 = Site.objects.filter(id=3).first()
        if site3:
            # Check if domain homefinderke.onrender.com is already taken by another site record to prevent unique constraints
            existing = Site.objects.filter(domain='homefinderke.onrender.com').exclude(id=3).first()
            if existing:
                existing.domain = 'temp-domain.local'
                existing.save()
            site3.domain = 'homefinderke.onrender.com'
            site3.name = 'HomeFinderKE'
            site3.save()
        else:
            # Check if domain homefinderke.onrender.com is already taken by another site record to prevent unique constraints
            existing = Site.objects.filter(domain='homefinderke.onrender.com').first()
            if existing:
                existing.domain = 'temp-domain.local'
                existing.save()
            Site.objects.get_or_create(id=3, defaults={'domain': 'homefinderke.onrender.com', 'name': 'HomeFinderKE'})
            
    except Exception as e:
        print(f"Skipping site setup: {e}")

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0028_alter_residencephoto_image'),
        ('sites', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(setup_default_site),
    ]
