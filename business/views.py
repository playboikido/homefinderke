import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from core.mpesa import initiate_stk_push

from .forms import (
    BusinessContactForm, BusinessEditForm, BusinessInfoForm, BusinessLocationForm,
    BusinessProductFormSet, BusinessServiceFormSet, BusinessVerificationForm,
)
from .models import (
    PLAN_CHOICES, PLAN_FEATURE_COPY, PLAN_HEADLINE_COUNT, PLAN_LIMITS, PLAN_PRICING,
    Business, BusinessAIUsage, BusinessBooking, BusinessCoupon, BusinessOrder, BusinessOrderItem,
    BusinessPayment, BusinessPromotion, BusinessProduct, BusinessQuotation,
    BusinessService, BusinessStaffMember, BusinessSubscription, BusinessVerificationDocument,
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
def business_reviews(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    can_reply = business.has_feature('reviews_reply')
    if request.method == 'POST' and can_reply:
        review = business.reviews.filter(pk=request.POST.get('review_id')).first()
        reply_text = request.POST.get('reply', '').strip()
        if review and reply_text:
            review.reply = reply_text
            review.replied_at = timezone.now()
            review.save(update_fields=['reply', 'replied_at'])
            messages.success(request, "Reply posted.")
        return redirect('business:reviews')

    reviews = business.reviews.select_related('user').all()
    return render(request, 'business/reviews.html', {
        'business': business, 'reviews': reviews, 'can_reply': can_reply, 'active_tab': 'reviews',
    })


@login_required
def business_analytics(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    now = timezone.now()
    events = business.analytics_events.filter(created_at__gte=now - timedelta(days=30))
    breakdown = {
        'profile_view':   events.filter(event_type='profile_view').count(),
        'phone_click':    events.filter(event_type='phone_click').count(),
        'whatsapp_click': events.filter(event_type='whatsapp_click').count(),
        'website_click':  events.filter(event_type='website_click').count(),
        'product_view':   events.filter(event_type='product_view').count(),
        'saved':          events.filter(event_type='saved').count(),
    }
    advanced = business.has_feature('advanced_analytics')
    top_products = business.products.order_by('-views_count')[:10 if advanced else 3]
    location_breakdown = None
    if advanced:
        location_breakdown = (
            events.exclude(location_hint='').values('location_hint')
            .annotate(count=Count('id')).order_by('-count')[:8]
        )
    return render(request, 'business/analytics.html', {
        'business': business, 'breakdown': breakdown, 'advanced': advanced,
        'top_products': top_products, 'location_breakdown': location_breakdown, 'active_tab': 'analytics',
    })


@login_required
def business_gallery(request):
    from .models import BusinessGalleryImage
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    limit = PLAN_LIMITS[business.plan]['gallery']
    photos = business.gallery_images.all()

    if request.method == 'POST':
        if 'delete_id' in request.POST:
            BusinessGalleryImage.objects.filter(pk=request.POST['delete_id'], business=business).delete()
            messages.success(request, "Photo removed.")
            return redirect('business:gallery')
        image = request.FILES.get('image')
        if image:
            if limit is not None and photos.count() >= limit:
                messages.error(request, f"Your {business.get_plan_display()} plan allows up to {limit} gallery photos. Upgrade to add more.")
            else:
                BusinessGalleryImage.objects.create(
                    business=business, image=image, caption=request.POST.get('caption', '').strip()
                )
                messages.success(request, "Photo uploaded.")
        return redirect('business:gallery')

    return render(request, 'business/gallery.html', {
        'business': business, 'photos': photos, 'limit': limit, 'active_tab': 'gallery',
    })


@login_required
def business_inquiries(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if not business.has_feature('inquiries'):
        return render(request, 'business/inquiries.html', {
            'business': business, 'locked': True, 'active_tab': 'inquiries',
        })

    if request.method == 'POST':
        inquiry = business.inquiries.filter(pk=request.POST.get('inquiry_id')).first()
        reply_text = request.POST.get('reply', '').strip()
        if inquiry and reply_text:
            inquiry.reply = reply_text
            inquiry.status = 'responded'
            inquiry.responded_at = timezone.now()
            inquiry.save(update_fields=['reply', 'status', 'responded_at'])
            messages.success(request, "Reply sent.")
        return redirect('business:inquiries')

    inquiries = business.inquiries.select_related('product', 'customer').all()
    return render(request, 'business/inquiries.html', {
        'business': business, 'inquiries': inquiries, 'locked': False, 'active_tab': 'inquiries',
    })


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


@login_required
def team_members(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    User = get_user_model()
    seat_limit = business.plan_limits['staff']  # None = unlimited (Enterprise)
    staff_qs = business.staff_members.select_related('user').all()
    seats_used = 1 + staff_qs.count()  # 1 = the owner's own seat

    if request.method == 'POST':
        if 'remove_id' in request.POST:
            BusinessStaffMember.objects.filter(pk=request.POST['remove_id'], business=business).delete()
            messages.success(request, "Staff member removed.")
            return redirect('business:team')

        email = request.POST.get('email', '').strip().lower()
        role = request.POST.get('role', 'staff')
        if role not in ('manager', 'staff'):
            role = 'staff'

        if seat_limit is not None and seats_used >= seat_limit:
            messages.error(request, f"Your current plan allows up to {seat_limit} staff account(s). Upgrade to add more.")
            return redirect('business:team')

        target_user = User.objects.filter(email__iexact=email).first()
        if not target_user:
            messages.error(request, "No HomeFinder KE account found with that email. They need to sign up first.")
        elif target_user == business.owner:
            messages.error(request, "That's the business owner — no need to add them as staff.")
        elif BusinessStaffMember.objects.filter(business=business, user=target_user).exists():
            messages.error(request, "That person is already on your team.")
        else:
            BusinessStaffMember.objects.create(business=business, user=target_user, role=role)
            messages.success(request, f"{target_user.email} added to your team.")
        return redirect('business:team')

    return render(request, 'business/team.html', {
        'business': business, 'staff_members': staff_qs, 'seats_used': seats_used,
        'seat_limit': seat_limit, 'active_tab': 'team',
    })


@login_required
def business_payments(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    payments = business.payments.all()
    subscription = getattr(business, 'subscription', None)
    return render(request, 'business/payments.html', {
        'business': business, 'payments': payments, 'subscription': subscription,
        'active_tab': 'payments',
    })

    if price is None:
        # Enterprise / custom pricing — sales-assisted, no automated payment
        BusinessPayment.objects.create(
            business=business, purpose='subscription_monthly', method='mpesa',
            amount=0, status='pending', plan=plan_slug,
        )
        messages.success(
            request,
            "Upgrade request received — our team will reach out shortly to confirm custom pricing.",
        )
        return redirect('business:dashboard')

    if not business.phone_number:
        messages.error(request, "Please add a phone number to your business profile before upgrading.")
        return redirect('business:edit')

    payment = BusinessPayment.objects.create(
        business=business, purpose='subscription_monthly', method='mpesa',
        amount=price, status='pending', plan=plan_slug,
    )

    result = initiate_stk_push(
        business.phone_number,
        price,
        callback_url=settings.MPESA_BUSINESS_CALLBACK_URL,
        account_reference=f"HFKE-{business.slug}"[:20],
        transaction_desc=f"{dict(PLAN_CHOICES)[plan_slug]} plan upgrade",
    )

    if result.get('ResponseCode') == '0':
        payment.checkout_request_id = result.get('CheckoutRequestID', '')
        payment.merchant_request_id = result.get('MerchantRequestID', '')
        payment.save(update_fields=['checkout_request_id', 'merchant_request_id'])
        messages.success(request, "Check your phone and enter your M-Pesa PIN to complete the upgrade.")
    else:
        payment.status = 'failed'
        payment.save(update_fields=['status'])
        messages.error(request, result.get('errorMessage', 'Could not start the payment. Please try again.'))

    return redirect('business:dashboard')


@csrf_exempt
@require_POST
def business_mpesa_callback(request):
    data = json.loads(request.body)
    result = data.get('Body', {}).get('stkCallback', {})
    checkout_id = result.get('CheckoutRequestID')

    try:
        payment = BusinessPayment.objects.get(checkout_request_id=checkout_id)
        if result.get('ResultCode') == 0:
            items = result.get('CallbackMetadata', {}).get('Item', [])
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    payment.mpesa_receipt = item.get('Value', '')
            payment.save(update_fields=['mpesa_receipt'])
            payment.activate()
        else:
            payment.status = 'failed'
            payment.save(update_fields=['status'])
    except BusinessPayment.DoesNotExist:
        pass

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

@login_required
def coupons_view(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if not business.has_feature('coupons'):
        return render(request, 'business/coupons.html', {
            'business': business, 'locked': True, 'active_tab': 'coupons',
        })

    if request.method == 'POST':
        if 'delete_id' in request.POST:
            BusinessCoupon.objects.filter(pk=request.POST['delete_id'], business=business).delete()
            messages.success(request, "Coupon deleted.")
            return redirect('business:coupons')

        if 'toggle_id' in request.POST:
            coupon = BusinessCoupon.objects.filter(pk=request.POST['toggle_id'], business=business).first()
            if coupon:
                coupon.is_active = not coupon.is_active
                coupon.save(update_fields=['is_active'])
            return redirect('business:coupons')

        code = request.POST.get('code', '').strip().upper()
        discount_type = request.POST.get('discount_type', 'percent')
        valid_from = request.POST.get('valid_from', '')
        valid_until = request.POST.get('valid_until', '')

        errors = []
        if not code or not code.isalnum():
            errors.append("Coupon code must be letters/numbers only.")
        elif BusinessCoupon.objects.filter(business=business, code=code).exists():
            errors.append("You already have a coupon with that code.")

        try:
            discount_value = float(request.POST.get('discount_value', ''))
            if discount_type == 'percent' and not (0 < discount_value <= 100):
                errors.append("Percentage discount must be between 1 and 100.")
            elif discount_value <= 0:
                errors.append("Discount value must be greater than 0.")
        except (TypeError, ValueError):
            errors.append("Enter a valid discount value.")
            discount_value = None

        if not valid_from or not valid_until:
            errors.append("Set both a start and end date.")
        elif valid_until < valid_from:
            errors.append("End date must be after start date.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            BusinessCoupon.objects.create(
                business=business, code=code, discount_type=discount_type,
                discount_value=discount_value, description=request.POST.get('description', '').strip(),
                max_uses=request.POST.get('max_uses') or None,
                valid_from=valid_from, valid_until=valid_until,
            )
            messages.success(request, f"Coupon {code} created.")
        return redirect('business:coupons')

    coupons = business.coupons.all()
    return render(request, 'business/coupons.html', {
        'business': business, 'coupons': coupons, 'locked': False, 'active_tab': 'coupons',
    })


@login_required
def promotions_view(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if not business.has_feature('promotions'):
        return render(request, 'business/promotions.html', {
            'business': business, 'locked': True, 'active_tab': 'promotions',
        })

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        placement = request.POST.get('placement', 'category_featured')
        starts_on = request.POST.get('starts_on', '')
        ends_on = request.POST.get('ends_on', '')

        valid_placements = {c for c, _ in BusinessPromotion.PLACEMENT_CHOICES}
        if placement not in valid_placements:
            placement = 'category_featured'
        if placement == 'homepage' and not business.has_feature('homepage_promotion'):
            messages.error(request, "Homepage placement requires the Premium plan.")
        elif not title or not starts_on or not ends_on:
            messages.error(request, "Fill in the title and both dates.")
        elif ends_on < starts_on:
            messages.error(request, "End date must be after start date.")
        else:
            BusinessPromotion.objects.create(
                business=business, title=title, placement=placement,
                starts_on=starts_on, ends_on=ends_on,
            )
            messages.success(request, "Promotion request submitted for review. We'll notify you once it's approved.")
        return redirect('business:promotions')

    promotions = business.promotions.all()
    return render(request, 'business/promotions.html', {
        'business': business, 'promotions': promotions, 'locked': False, 'active_tab': 'promotions',
        'can_request_homepage': business.has_feature('homepage_promotion'),
    })

@login_required
def services_manage(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    queryset = BusinessService.objects.filter(business=business)
    limit = business.plan_limits['services']

    if request.method == 'POST':
        formset = BusinessServiceFormSet(request.POST, request.FILES, queryset=queryset)
        if formset.is_valid():
            existing_active = business.services.filter(is_available=True).count()
            new_count = sum(
                1 for f in formset.forms
                if f.cleaned_data and not f.cleaned_data.get('DELETE')
                and f.cleaned_data.get('name') and not f.cleaned_data.get('id')
            )
            if limit is not None and (existing_active + new_count) > limit:
                messages.error(request, f"Your current plan allows up to {limit} services. Upgrade to add more.")
            else:
                services = formset.save(commit=False)
                for service in services:
                    service.business = business
                    service.save()
                for obj in formset.deleted_objects:
                    obj.delete()
                messages.success(request, "Services updated.")
                return redirect('business:services')
    else:
        formset = BusinessServiceFormSet(queryset=queryset)

    return render(request, 'business/services.html', {
        'formset': formset, 'business': business, 'service_limit': limit, 'active_tab': 'services',
    })


@login_required
def bookings_view(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if not business.has_feature('bookings'):
        return render(request, 'business/bookings.html', {
            'business': business, 'locked': True, 'active_tab': 'bookings',
        })

    if request.method == 'POST':
        booking = business.bookings.filter(pk=request.POST.get('booking_id')).first()
        new_status = request.POST.get('status', '')
        valid_statuses = {c for c, _ in BusinessBooking.STATUS_CHOICES}
        if booking and new_status in valid_statuses:
            booking.status = new_status
            booking.save(update_fields=['status'])
            messages.success(request, "Booking updated.")
        return redirect('business:bookings')

    bookings = business.bookings.select_related('service', 'customer').all()
    return render(request, 'business/bookings.html', {
        'business': business, 'bookings': bookings, 'locked': False, 'active_tab': 'bookings',
    })

@login_required
def quotations_view(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if not business.has_feature('inquiries'):
        return render(request, 'business/quotations.html', {
            'business': business, 'locked': True, 'active_tab': 'quotations',
        })

    if request.method == 'POST':
        quotation = business.quotations.filter(pk=request.POST.get('quotation_id')).first()
        if quotation:
            amount = request.POST.get('quoted_amount', '').strip()
            notes = request.POST.get('quote_notes', '').strip()
            action = request.POST.get('action', '')
            if action == 'send_quote' and amount:
                try:
                    quotation.quoted_amount = float(amount)
                    quotation.quote_notes = notes
                    quotation.status = 'quoted'
                    quotation.responded_at = timezone.now()
                    quotation.save(update_fields=['quoted_amount', 'quote_notes', 'status', 'responded_at'])
                    messages.success(request, "Quote sent.")
                except (TypeError, ValueError):
                    messages.error(request, "Enter a valid quote amount.")
            elif action == 'decline':
                quotation.status = 'declined'
                quotation.responded_at = timezone.now()
                quotation.save(update_fields=['status', 'responded_at'])
                messages.success(request, "Quotation declined.")
        return redirect('business:quotations')

    quotations = business.quotations.select_related('product', 'service').all()
    return render(request, 'business/quotations.html', {
        'business': business, 'quotations': quotations, 'locked': False, 'active_tab': 'quotations',
    })


def _recalc_order_total(order):
    total = sum(item.quantity * item.unit_price for item in order.items.all())
    order.total_amount = total
    order.save(update_fields=['total_amount'])


@login_required
def orders_view(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if not business.has_feature('order_management'):
        return render(request, 'business/orders.html', {
            'business': business, 'locked': True, 'active_tab': 'orders',
        })

    if request.method == 'POST':
        if 'new_order' in request.POST:
            customer_name = request.POST.get('customer_name', '').strip()
            product_id = request.POST.get('product_id', '')
            quantity = request.POST.get('quantity', '1')
            unit_price = request.POST.get('unit_price', '')

            product = business.products.filter(pk=product_id).first()
            try:
                quantity = max(1, int(quantity))
                unit_price = float(unit_price) if unit_price else float(product.price or 0) if product else 0
            except (TypeError, ValueError):
                messages.error(request, "Enter a valid quantity and price.")
                return redirect('business:orders')

            if not customer_name or not product:
                messages.error(request, "Customer name and a valid product are required.")
                return redirect('business:orders')

            order = BusinessOrder.objects.create(
                business=business, customer_name=customer_name,
                customer_phone=request.POST.get('customer_phone', '').strip(),
                delivery_address=request.POST.get('delivery_address', '').strip(),
            )
            BusinessOrderItem.objects.create(
                order=order, product=product, product_name=product.name,
                quantity=quantity, unit_price=unit_price,
            )
            _recalc_order_total(order)
            messages.success(request, f"Order created for {customer_name}.")

        elif 'add_item' in request.POST:
            order = business.orders.filter(pk=request.POST.get('order_id')).first()
            product = business.products.filter(pk=request.POST.get('product_id')).first()
            if order and product:
                try:
                    quantity = max(1, int(request.POST.get('quantity', '1')))
                    unit_price = float(request.POST.get('unit_price') or product.price or 0)
                    BusinessOrderItem.objects.create(
                        order=order, product=product, product_name=product.name,
                        quantity=quantity, unit_price=unit_price,
                    )
                    _recalc_order_total(order)
                    messages.success(request, "Item added.")
                except (TypeError, ValueError):
                    messages.error(request, "Enter a valid quantity and price.")

        elif 'update_status' in request.POST:
            order = business.orders.filter(pk=request.POST.get('order_id')).first()
            new_status = request.POST.get('status', '')
            valid_statuses = {c for c, _ in BusinessOrder.STATUS_CHOICES}
            if order and new_status in valid_statuses:
                order.status = new_status
                order.save(update_fields=['status'])
                messages.success(request, "Order updated.")

        return redirect('business:orders')

    orders = business.orders.prefetch_related('items').all()
    return render(request, 'business/orders.html', {
        'business': business, 'orders': orders, 'products': business.products.filter(is_available=True),
        'locked': False, 'active_tab': 'orders',
    })

AI_TASK_PROMPTS = {
    'product_description': (
        "You write concise, honest product/service listing descriptions for small businesses on a "
        "Kenyan home-services marketplace. Keep it under 80 words, factual (don't invent details not "
        "given), and appealing to Kenyan customers. Return plain text only, no markdown."
    ),
    'seo': (
        "You generate SEO metadata for a Kenyan business's directory profile. Given the business info, "
        "return exactly two lines: 'Title: ...' (under 60 characters) and 'Keywords: ...' (5-8 comma-"
        "separated keywords relevant to Kenyan search intent). No other text."
    ),
    'social_caption': (
        "You write short, engaging social media captions for a Kenyan small business. Match the tone to "
        "the requested platform (Facebook posts can be slightly longer and conversational, Instagram "
        "captions are punchy with 2-4 relevant hashtags, WhatsApp adverts are short and direct with a "
        "clear call-to-action). Return plain text only, no markdown, no quotation marks around it."
    ),
}


def _business_ai_quota_check(business):
    """Returns (allowed: bool, usage: BusinessAIUsage, limit: int|None)."""
    from django.utils import timezone
    limit = business.plan_limits.get('ai_generations', 0)
    current_month = timezone.now().strftime('%Y-%m')
    usage, _ = BusinessAIUsage.objects.get_or_create(business=business, defaults={'month': current_month})
    if usage.month != current_month:
        usage.month = current_month
        usage.generations_used = 0
        usage.save(update_fields=['month', 'generations_used'])
    if limit is not None and usage.generations_used >= limit:
        return False, usage, limit
    return True, usage, limit


@login_required
def ai_assistant_view(request):
    business = _get_business_or_redirect(request)
    if not business:
        return redirect('business:onboarding_start')
    if not business.onboarding_complete:
        return redirect(STEP_URLS[business.onboarding_step])

    if not business.has_feature('ai_assistant'):
        return render(request, 'business/ai_assistant.html', {
            'business': business, 'locked': True, 'active_tab': 'ai_assistant',
        })

    from core.views import _get_nvidia_client, check_submission_rate_limit

    result = None
    if request.method == 'POST':
        if not check_submission_rate_limit(request, 'business_ai_assistant', limit=20, window_seconds=3600):
            messages.error(request, "Too many AI requests. Please slow down and try again shortly.")
            return redirect('business:ai_assistant')

        task = request.POST.get('task', '')
        user_input = request.POST.get('user_input', '').strip()
        platform = request.POST.get('platform', 'facebook')

        if task not in AI_TASK_PROMPTS:
            messages.error(request, "Unknown AI task.")
            return redirect('business:ai_assistant')
        if not user_input:
            messages.error(request, "Tell the assistant what to work with first.")
            return redirect('business:ai_assistant')

        allowed, usage, limit = _business_ai_quota_check(business)
        if not allowed:
            messages.error(request, f"You've used all {limit} AI generations for this month on your {business.get_plan_display()} plan. Upgrade for more.")
            return redirect('business:ai_assistant')

        try:
            client = _get_nvidia_client()
            user_prompt = user_input
            if task == 'social_caption':
                user_prompt = f"Platform: {platform}\n\nBusiness/context: {user_input}"

            response = client.chat.completions.create(
                model="z-ai/glm-5.2",
                messages=[
                    {"role": "system", "content": AI_TASK_PROMPTS[task]},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.5,
                max_tokens=250,
            )
            result = response.choices[0].message.content.strip()
            usage.generations_used += 1
            usage.save(update_fields=['generations_used'])
        except Exception as e:
            print("BUSINESS AI ASSISTANT ERROR:", e)
            messages.error(request, "The AI assistant is unavailable right now. Please try again shortly.")

    _, usage, limit = _business_ai_quota_check(business)
    return render(request, 'business/ai_assistant.html', {
        'business': business, 'locked': False, 'active_tab': 'ai_assistant',
        'result': result, 'generations_used': usage.generations_used, 'generation_limit': limit,
    })