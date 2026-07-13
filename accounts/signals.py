import logging

from django.contrib.auth.signals import user_logged_in
from django.core.mail import send_mail
from django.dispatch import receiver

from .models import KnownDevice

logger = logging.getLogger(__name__)


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


@receiver(user_logged_in)
def check_new_device_login(sender, request, user, **kwargs):
    ip_address = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "unknown")[:255]
    fingerprint = KnownDevice.make_fingerprint(ip_address, user_agent)

    device, created = KnownDevice.objects.get_or_create(
        user=user,
        fingerprint=fingerprint,
        defaults={"ip_address": ip_address, "user_agent": user_agent},
    )

    if created:
        try:
            send_mail(
                subject="New login to your Hompindake account",
                message=(
                    f"Hi {user.get_username()},\n\n"
                    f"We noticed a login to your account from a new device or location.\n\n"
                    f"IP address: {ip_address}\n"
                    f"Device: {user_agent}\n\n"
                    f"If this was you, no action is needed. "
                    f"If you don't recognize this activity, please reset your password immediately."
                ),
                from_email=None,  # uses DEFAULT_FROM_EMAIL
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error("Failed to send new-device login email to %s: %s", user.email, e)