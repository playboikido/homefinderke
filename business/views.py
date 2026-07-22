from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import (
    BusinessInfoForm,
    BusinessContactForm,
    BusinessLocationForm,
    BusinessProductFormSet,
    BusinessVerificationForm,
)
from .models import Business, BusinessInquiry, BusinessAnalyticsEvent


def choose(request):
    """Split-screen entry point: Resident vs Business."""
    return render(request, 'business/choose.html')


@login_required
def onboarding_start(request):
    business = request.user.businesses.first()
    if not business:
        business = Business.objects.create(owner=request.user, name='', onboarding_step=1)
        profile = getattr(request.user, 'profile', None)
        if profile:
            profile.account_type = 'business'
            profile.save(update_fields=['account_type'])

    step_urls = {
        1: 'business:onboarding_info',
        2: 'business:onboarding_contact',
        3: 'business:onboarding_location',
        4: 'business:onboarding_products',
        5: 'business:onboarding_verification',
    }
    if business.onboarding_complete:
        return redirect('business:dashboard')
    return redirect(step_urls.get(business.onboarding_step, 'business:onboarding_info'))


def _get_business_or_redirect(request):
    return request.user.businesses.first()


@login_required
def onboarding_info(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if request.method == 'POST':
        form = BusinessInfoForm(request.POST, request.FILES, instance=business)
        if form.is_valid():
            business = form.save(commit=False)
            business.onboarding_step = max(business.onboarding_step, 2)
            business.save()
            return redirect('business:onboarding_contact')
    else:
        form = BusinessInfoForm(instance=business)
    return render(request, 'business/onboarding/step1_info.html', {'form': form, 'step': 1})


@login_required
def onboarding_contact(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if request.method == 'POST':
        form = BusinessContactForm(request.POST, instance=business)
        if form.is_valid():
            business = form.save(commit=False)
            business.onboarding_step = max(business.onboarding_step, 3)
            business.save()
            return redirect('business:onboarding_location')
    else:
        form = BusinessContactForm(instance=business)
    return render(request, 'business/onboarding/step2_contact.html', {'form': form, 'step': 2})


@login_required
def onboarding_location(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if request.method == 'POST':
        form = BusinessLocationForm(request.POST, instance=business)
        if form.is_valid():
            business = form.save(commit=False)
            business.onboarding_step = max(business.onboarding_step, 4)
            business.save()
            return redirect('business:onboarding_products')
    else:
        form = BusinessLocationForm(instance=business)
    return render(request, 'business/onboarding/step3_location.html', {'form': form, 'step': 3})


@login_required
def onboarding_products(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if request.method == 'POST':
        if 'skip' in request.POST:
            business.onboarding_step = max(business.onboarding_step, 5)
            business.save(update_fields=['onboarding_step'])
            return redirect('business:onboarding_verification')
        formset = BusinessProductFormSet(
            request.POST, request.FILES,
            queryset=business.products.all(),
        )
        if formset.is_valid():
            products = formset.save(commit=False)
            for p in products:
                p.business = business
                p.save()
            for p in formset.deleted_objects:
                p.delete()
            business.onboarding_step = max(business.onboarding_step, 5)
            business.save(update_fields=['onboarding_step'])
            return redirect('business:onboarding_verification')
    else:
        formset = BusinessProductFormSet(queryset=business.products.all())
    limit = business.plan_limits['products']
    return render(request, 'business/onboarding/step4_products.html', {
        'formset': formset, 'step': 4, 'product_limit': limit,
    })


@login_required
def onboarding_verification(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if request.method == 'POST':
        if 'skip' in request.POST:
            business.onboarding_complete = True
            business.save(update_fields=['onboarding_complete'])
            messages.success(request, 'Your business workspace is ready. You can submit verification documents anytime from Settings.')
            return redirect('business:dashboard')
        form = BusinessVerificationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(business)
            business.onboarding_complete = True
            business.verification_status = 'pending'
            business.save(update_fields=['onboarding_complete', 'verification_status'])
            messages.success(request, 'Documents submitted. Your business is now pending verification.')
            return redirect('business:dashboard')
    else:
        form = BusinessVerificationForm()
    return render(request, 'business/onboarding/step5_verification.html', {'form': form, 'step': 5})


@login_required
def dashboard(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect('business:onboarding_start')

    stats = {
        'profile_views': business.analytics_events.filter(event_type='profile_view').count(),
        'phone_clicks': business.analytics_events.filter(event_type='phone_click').count(),
        'whatsapp_clicks': business.analytics_events.filter(event_type='whatsapp_click').count(),
        'website_visits': business.analytics_events.filter(event_type='website_click').count(),
        'inquiries': business.inquiries.count(),
        'saved_count': business.favorited_by.count(),
        'review_count': business.review_count,
        'average_rating': business.average_rating,
    }
    recent_inquiries = business.inquiries.all()[:5]
    return render(request, 'business/dashboard.html', {
        'business': business, 'stats': stats, 'recent_inquiries': recent_inquiries,
    })