from .models import Notification
from django.core.exceptions import ObjectDoesNotExist

def notification_count(request):

    if hasattr(request, 'user') and request.user.is_authenticated:

        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        return {
            'unread_notifications': count
        }

    return {
        'unread_notifications': 0
    }

def business_context(request):
    """Adds the caller's business + subscription plan to templates (business accounts only)."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile and profile.account_type == 'business':
            business = request.user.businesses.first()
            plan = 'starter'
            if business is not None:
                try:
                    plan = business.subscription.plan
                except ObjectDoesNotExist:
                    plan = 'starter'
            return {'nav_business': business, 'nav_business_plan': plan}
    return {'nav_business': None, 'nav_business_plan': None}