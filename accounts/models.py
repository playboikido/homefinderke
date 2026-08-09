import hashlib

from django.conf import settings
from django.db import models


class KnownDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="known_devices")
    fingerprint = models.CharField(max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "fingerprint")

    @staticmethod
    def make_fingerprint(ip_address, user_agent):
        raw = f"{ip_address}:{user_agent}"
        return hashlib.sha256(raw.encode()).hexdigest()