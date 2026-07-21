from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
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
                messages.warning(
                    request,
                    '🔒 Admin accounts require two-factor authentication. Please set it up below to continue.'
                )
                return redirect(reverse('mfa_activate_totp'))
        return self.get_response(request)
    
STAFF_SESSION_AGE_SECONDS = 60 * 60 * 2  # 2 hours for admin accounts
DEFAULT_SESSION_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days for everyone else (Django's normal default)


class StaffShortSessionMiddleware:
    """Shortens session lifetime specifically for staff/help-admin accounts,
    without affecting regular tenant/landlord session length."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            is_admin_account = user.is_staff or user.email == 'homefinder.ke.help@gmail.com'
            if is_admin_account:
                request.session.set_expiry(STAFF_SESSION_AGE_SECONDS)
            else:
                request.session.set_expiry(DEFAULT_SESSION_AGE_SECONDS)
        return response    