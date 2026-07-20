from django.shortcuts import redirect
from django.urls import reverse
from allauth.mfa.utils import is_mfa_enabled

STAFF_URL_PREFIXES = ('/control-panel-2947/', '/admin-dashboard/', '/staff-tools/')
MFA_EXEMPT_PATHS = ('/accounts/2fa/', '/accounts/logout/')


class RequireStaffMFAMiddleware:
    """Blocks staff/help-admin from admin routes until they've set up 2FA."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(STAFF_URL_PREFIXES) and not request.path.startswith(MFA_EXEMPT_PATHS):
            user = request.user
            is_admin_account = user.is_authenticated and (
                user.is_staff or user.email == 'homefinder.ke.help@gmail.com'
            )
            if is_admin_account and not is_mfa_enabled(user):
                return redirect(reverse('account_login') + '?mfa_required=1')
        return self.get_response(request)