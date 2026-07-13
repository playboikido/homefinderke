import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger(__name__)


class SafeAccountAdapter(DefaultAccountAdapter):
    """
    Wraps allauth's email sending so that SMTP/network failures
    (e.g. Render's outbound network blocking SMTP) never crash a
    request. Login, signup, verification, password reset, and the
    'account already exists' flow will all succeed even if the
    email itself fails to send.
    """

    def send_mail(self, template_prefix, email, context):
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as e:
            logger.error(
                "Failed to send account email (template=%s, to=%s): %s",
                template_prefix, email, e,
            )


class SafeSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Social login (Google, etc.) adapter. Doesn't send mail itself,
    but kept as a hook point in case you add pre_social_login logic
    later. Safe to use as-is.
    """
    pass