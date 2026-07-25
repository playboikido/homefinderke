from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import (
    BusinessContactForm, BusinessEditForm, BusinessInfoForm, BusinessLocationForm,
    BusinessProductFormSet, BusinessVerificationForm,
)
from .models import (
    PLAN_CHOICES, PLAN_FEATURE_COPY, PLAN_HEADLINE_COUNT, PLAN_LIMITS, PLAN_PRICING,
    Business, BusinessPayment, BusinessProduct, BusinessSubscription, BusinessVerificationDocument,
)

STEP_URLS = {
    1: 'business:onboarding_info',
    2: 'business:onboarding_contact',
    3: 'business:onboarding_location',
    4: 'business:onboarding_products',
    5: 'business:onboarding_verification',
}


def choose_view(request):
    """Split-screen entry point: Resident vs Business."""
    next_url = request.GET.get('next', '')
    return render(request, 'business/choose.html', {'next_url': next_url})


def _get_business_or_redirect(request):
    """Returns the caller's own business, or None. Caller decides where to send a None."""
    return request.user.businesses.first()


def _guard_step(business, requested_step):
    """
    Block access to any step ahead of the frontier the business has actually
    reached. Once onboarding is fully complete, every step becomes editable
    (going back to fix something is fine; skipping ahead on the way there is not).
    """
    if business.onboarding_complete:
        return None
    if requested_step > business.onboarding_step:
        return redirect(STEP_URLS[business.onboarding_step])
    return None


def _advance_step(business, completed_step):
    if business.onboarding_step == completed_step and not business.onboarding_complete:
        business.onboarding_step = completed_step + 1
    business.save()


@login_required
def onboarding_start(request):
    business = request.user.businesses.first()
    if not business:
        business = Business.objects.create(owner=request.user, name='', onboarding_step=1)
        profile = getattr(request.user, 'profile', None)
        if profile:
            profile.account_type = 'business'
            profile.save(update_fields=['account_type'])

    if business.onboarding_complete:
        return redirect('business:dashboard')
    return redirect(STEP_URLS[business.onboarding_step])


@login_required
def onboarding_info(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    guard = _guard_step(business, 1)
    if guard:
        return guard

    if request.method == 'POST':
        form = BusinessInfoForm(request.POST, request.FILES, instance=business)
        if form.is_valid():
            form.save()
            _advance_step(business, 1)
            return redirect('business:onboarding_contact')
    else:
        form = BusinessInfoForm(instance=business)

    return render(request, 'business/onboarding/step1_info.html', {'form': form, 'step': 1, 'business': business})


@login_required
def onboarding_contact(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    guard = _guard_step(business, 2)
    if guard:
        return guard

    if request.method == 'POST':
        form = BusinessContactForm(request.POST, instance=business)
        if form.is_valid():
            form.save()
            _advance_step(business, 2)
            return redirect('business:onboarding_location')
    else:
        form = BusinessContactForm(instance=business)

    return render(request, 'business/onboarding/step2_contact.html', {'form': form, 'step': 2, 'business': business})


@login_required
def onboarding_location(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    guard = _guard_step(business, 3)
    if guard:
        return guard

    if request.method == 'POST':
        form = BusinessLocationForm(request.POST, instance=business)
        if form.is_valid():
            form.save()
            _advance_step(business, 3)
            return redirect('business:onboarding_products')
    else:
        form = BusinessLocationForm(instance=business)

    return render(request, 'business/onboarding/step3_location.html', {'form': form, 'step': 3, 'business': business})


@login_required
def onboarding_products(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    guard = _guard_step(business, 4)
    if guard:
        return guard

    queryset = BusinessProduct.objects.filter(business=business)
    limit = business.plan_limits['products']

    if request.method == 'POST':
        if 'skip' in request.POST:
            _advance_step(business, 4)
            return redirect('business:onboarding_verification')

        formset = BusinessProductFormSet(request.POST, request.FILES, queryset=queryset)
        if formset.is_valid():
            existing_active = business.products.filter(is_available=True).count()
            new_count = sum(
                1 for f in formset.forms
                if f.cleaned_data and not f.cleaned_data.get('DELETE')
                and f.cleaned_data.get('name') and not f.cleaned_data.get('id')
            )
            if limit is not None and (existing_active + new_count) > limit:
                messages.error(request, f"Your current plan allows up to {limit} products. Upgrade to add more.")
            else:
                products = formset.save(commit=False)
                for product in products:
                    product.business = business
                    product.save()
                for obj in formset.deleted_objects:
                    obj.delete()
                _advance_step(business, 4)
                return redirect('business:onboarding_verification')
    else:
        formset = BusinessProductFormSet(queryset=queryset)

    return render(request, 'business/onboarding/step4_products.html', {
        'formset': formset, 'step': 4, 'business': business, 'product_limit': limit,
    })


@login_required
def onboarding_verification(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    guard = _guard_step(business, 5)
    if guard:
        return guard

    if request.method == 'POST':
        if 'skip' in request.POST:
            business.onboarding_complete = True
            business.save(update_fields=['onboarding_complete'])
            messages.success(request, "Your business workspace is ready. You can submit verification documents anytime from Settings.")
            return redirect('business:dashboard')

        form = BusinessVerificationForm(request.POST, request.FILES)
        if form.is_valid():
            # doc_type choices on BusinessVerificationDocument match these field
            # names exactly, so no translation map is needed.
            for field_name in ('registration_certificate', 'kra_pin', 'business_permit', 'national_id'):
                uploaded = form.cleaned_data.get(field_name)
                if uploaded:
                    BusinessVerificationDocument.objects.update_or_create(
                        business=business, doc_type=field_name, defaults={'file': uploaded},
                    )
            business.onboarding_complete = True
            business.verification_status = 'pending'
            business.save(update_fields=['onboarding_complete', 'verification_status'])
            messages.success(request, "Documents submitted. Your business is now pending verification.")
            return redirect('business:dashboard')
    else:
        form = BusinessVerificationForm()

    return render(request, 'business/onboarding/step5_verification.html', {'form': form, 'step': 5, 'business': business})


@login_required
def dashboard(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    now = timezone.now()
    last_30, prev_30 = now - timedelta(days=30), now - timedelta(days=60)

    def trend(event_type=None, inquiries=False):
        qs = business.inquiries if inquiries else business.analytics_events.filter(event_type=event_type)
        current = qs.filter(created_at__gte=last_30).count()
        previous = qs.filter(created_at__gte=prev_30, created_at__lt=last_30).count()
        pct = round(((current - previous) / previous) * 100) if previous else (100 if current else 0)
        return pct

    stats = {
        'profile_views': business.analytics_events.filter(event_type='profile_view').count(),
        'phone_clicks': business.analytics_events.filter(event_type='phone_click').count(),
        'whatsapp_clicks': business.analytics_events.filter(event_type='whatsapp_click').count(),
        'website_visits': business.analytics_events.filter(event_type='website_click').count(),
        'inquiries': business.inquiries.count(),
        'saved_count': business.favorited_by.count(),
        'review_count': business.review_count,
        'average_rating': business.average_rating,
        'product_count': business.product_count,
    }
    trends = {
        'profile_views': trend('profile_view'),
        'phone_clicks': trend('phone_click'),
        'whatsapp_clicks': trend('whatsapp_click'),
        'inquiries': trend(inquiries=True),
    }

    show_analytics = business.has_feature('analytics')
    chart_points, chart_max = '', 0
    if show_analytics:
        events = (business.analytics_events
                  .filter(event_type='profile_view', created_at__gte=last_30)
                  .annotate(day=TruncDate('created_at'))
                  .values('day').annotate(count=Count('id')))
        by_day = {e['day']: e['count'] for e in events}
        today = now.date()
        daily = [by_day.get(today - timedelta(days=i), 0) for i in range(29, -1, -1)]
        chart_max = max(daily) or 1
        width, height, step = 560, 140, 560 / 29
        chart_points = ' '.join(
            f"{round(i * step, 1)},{round(height - (v / chart_max) * (height - 20) - 10, 1)}"
            for i, v in enumerate(daily)
        )

    top_products = business.products.order_by('-views_count')[:4]
    recent_inquiries = business.inquiries.all()[:5]
    subscription = getattr(business, 'subscription', None)

    notifications = []
    for inquiry in business.inquiries.filter(status='new')[:3]:
        notifications.append({'icon': '💬', 'text': f'New inquiry from {inquiry.customer_name}', 'date': inquiry.created_at})
    if subscription and subscription.renewal_date:
        days_left = (subscription.renewal_date - now.date()).days
        if 0 <= days_left <= 14:
            notifications.append({'icon': '⏰', 'text': f'{business.get_plan_display()} plan renews in {days_left} days', 'date': now})
    if business.verification_status == 'pending':
        notifications.append({'icon': '✅', 'text': 'Verification documents are under review', 'date': now})
    notifications.sort(key=lambda n: n['date'], reverse=True)

    return render(request, 'business/dashboard.html', {
        'business': business, 'stats': stats, 'trends': trends,
        'recent_inquiries': recent_inquiries, 'show_analytics': show_analytics,
        'top_products': top_products, 'chart_points': chart_points, 'chart_max': chart_max,
        'notifications': notifications, 'subscription': subscription, 'active_tab': 'dashboard',
    })

@login_required
def business_edit(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if request.method == 'POST':
        form = BusinessEditForm(request.POST, request.FILES, instance=business)
        if form.is_valid():
            form.save()
            messages.success(request, "Business details updated.")
            return redirect('business:dashboard')
    else:
        form = BusinessEditForm(instance=business)

    return render(request, 'business/edit.html', {'form': form, 'business': business})


@login_required
def business_settings(request):
    from .forms import BusinessSettingsForm
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if request.method == 'POST':
        form = BusinessSettingsForm(request.POST, instance=business)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved.")
            return redirect('business:settings')
    else:
        form = BusinessSettingsForm(instance=business)

    return render(request, 'business/settings.html', {'form': form, 'business': business})


@login_required
def products_manage(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    queryset = BusinessProduct.objects.filter(business=business)
    limit = business.plan_limits['products']

    if request.method == 'POST':
        formset = BusinessProductFormSet(request.POST, request.FILES, queryset=queryset)
        if formset.is_valid():
            existing_active = business.products.filter(is_available=True).count()
            new_count = sum(
                1 for f in formset.forms
                if f.cleaned_data and not f.cleaned_data.get('DELETE')
                and f.cleaned_data.get('name') and not f.cleaned_data.get('id')
            )
            if limit is not None and (existing_active + new_count) > limit:
                messages.error(request, f"Your current plan allows up to {limit} products. Upgrade to add more.")
            else:
                products = formset.save(commit=False)
                for product in products:
                    product.business = business
                    product.save()
                for obj in formset.deleted_objects:
                    obj.delete()
                messages.success(request, "Products updated.")
                return redirect('business:products')
    else:
        formset = BusinessProductFormSet(queryset=queryset)

    return render(request, 'business/products.html', {
        'formset': formset, 'business': business, 'product_limit': limit,
    })


@login_required
def plans_view(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')

    plans = [
        {
            'slug': slug,
            'name': label,
            'monthly': PLAN_PRICING[slug]['monthly'],
            'yearly': PLAN_PRICING[slug]['yearly'],
            'limits': PLAN_LIMITS[slug],
            'is_current': business.plan == slug,
            'headline_features': PLAN_FEATURE_COPY[slug][:PLAN_HEADLINE_COUNT],
            'extra_features': PLAN_FEATURE_COPY[slug][PLAN_HEADLINE_COUNT:],
        }
        for slug, label in PLAN_CHOICES
    ]
    return render(request, 'business/plans.html', {'business': business, 'plans': plans})


@login_required
def request_upgrade(request, plan_slug):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')

    valid_slugs = {slug for slug, _ in PLAN_CHOICES}
    if plan_slug not in valid_slugs:
        messages.error(request, "That plan doesn't exist.")
        return redirect('business:plans')

    if plan_slug == 'starter':
        business.plan = 'starter'
        business.save(update_fields=['plan'])
        BusinessSubscription.objects.update_or_create(
            business=business, defaults={'plan': 'starter', 'status': 'active'},
        )
        messages.success(request, "You're now on the Starter plan.")
        return redirect('business:dashboard')

    price = PLAN_PRICING[plan_slug]['monthly']
    BusinessPayment.objects.create(
        business=business,
        purpose='subscription_monthly',
        method='mpesa',
        amount=price or 0,
        status='pending',
    )
    messages.success(
        request,
        f"Upgrade request for {dict(PLAN_CHOICES)[plan_slug]} received — our team will reach out shortly "
        f"by phone or WhatsApp to complete payment{' (custom pricing — we\u2019ll confirm the amount with you)' if price is None else ''}.",
    )
    return redirect('business:dashboard')