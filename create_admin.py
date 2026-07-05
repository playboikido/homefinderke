import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'homefinderke.settings')  # Replace with your true folder name
django.setup()

from django.contrib.auth.models import User

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'shakido_admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@shakido.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'ShakidoAdmin2026!')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' created successfully!")
else:
    print(f"Superuser '{username}' already exists.")