from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import Http404, HttpResponse
from .models import Residence, ResidenceReport, UserReport
from .models import Residence, ResidenceReport, ResidenceView
from .forms import ResidenceForm, ResidenceReportForm, MoverForm, FurnitureVendorForm, MoverSponsorForm, FurnitureVendorSponsorForm
from django.contrib import messages
from .models import Residence, ResidenceReport, Favorite
from django.db.models import Sum
from django.contrib.auth.models import User
from .models import Review
from .forms import ReviewForm
from django.db.models import Sum, Prefetch
from django.core.paginator import Paginator
from .forms import ProfileForm
from .models import Residence, Profile
from django.core.mail import send_mail
from django.conf import settings
from .models import ResidencePhoto, Mover, FurnitureVendor, MoverProduct, FurnitureProduct, MoverGalleryImage, FurnitureGalleryImage
from django.contrib import messages
from .forms import ContactForm
from django.contrib.auth.decorators import login_required
from .models import Notification
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
import json
import base64
from openai import OpenAI
from .watermark import watermark_image
# ─── AI NVIDIA helpers ──────────────────────────────────────────────────────
def _get_nvidia_client():
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=settings.NVIDIA_API_KEY)

def _ai_fraud_check(residence):
    """Use NVIDIA to flag suspicious listings. Returns (is_fraud, reason)."""
    try:
        client = _get_nvidia_client()
        prompt = (
            f"You are a fraud and quality-check assistant for a Kenyan property rental site. "
            f"Analyze this listing and determine if it looks fraudulent, suspicious, or has "
            f"security-claim inconsistencies:\n\n"
            f"Name: {residence.name}\n"
            f"County: {residence.county}, Town: {residence.town}\n"
            f"Rent: KSh {residence.rent_price}/month\n"
            f"Deposit: KSh {residence.deposit_amount}\n"
            f"Landmark: {residence.landmark}\n"
            f"Description: {residence.description}\n"
            f"Claimed security features: "
            f"Gated community = {residence.gated_community}, "
            f"CCTV = {residence.cctv_available}, "
            f"Security guard = {residence.security_guard}\n\n"
            f"Red flags to look for: unrealistically low rent for the area, requests for wire transfers, "
            f"Western Union, PayPal or Bitcoin payment mentions, asking to contact via WhatsApp only before viewing, "
            f"too-good-to-be-true language, suspicious contact instructions, OR a description that contradicts "
            f"the claimed security features (e.g. description mentions no security/open compound but gated "
            f"community is marked true, or claims 'high security' with no security features ticked at all).\n\n"
            f"Respond with JSON only, no markdown: {{\"fraud\": true/false, \"reason\": \"short explanation\"}}\n"
            f"If rent for a 1-bedroom in Nairobi is below KSh 5,000 or a bedsitter below KSh 2,000, flag it."
        )
        response = client.chat.completions.create(
            model="z-ai/glm-5.2",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
        )
        text = response.choices[0].message.content.strip().strip('`').replace('json', '').strip()
        data = json.loads(text)
        return data.get('fraud', False), data.get('reason', '')
    except Exception as e:
        print("AI FRAUD CHECK ERROR:", e)
        return False, ''

def _ai_image_check(image_field):
    """Use an NVIDIA vision model to check if the image is a real property photo."""
    try:
        import base64
        client = _get_nvidia_client()
        image_bytes = image_field.read()
        image_field.seek(0)
        b64 = base64.b64encode(image_bytes).decode('utf-8')

        response = client.chat.completions.create(
            model="meta/llama-3.2-90b-vision-instruct",  # confirm this ID on build.nvidia.com first
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (
                            "You are a property image quality checker. Look at this image and determine: "
                            "1) Is it a real photo of a house/apartment/room/exterior? "
                            "2) Is it clear and good quality (not blurry, not a screenshot, not a cartoon/meme)? "
                            "Respond with JSON only, no markdown: {\"status\": \"passed\" or \"failed\", \"feedback\": \"short reason\"}"
                        )},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=80,
        )
        text = response.choices[0].message.content.strip().strip('`').replace('json', '').strip()
        import json
        data = json.loads(text)
        return data.get('status', 'unchecked'), data.get('feedback', '')
    except Exception as e:
        print("AI IMAGE CHECK ERROR:", e)
        return 'unchecked', ''

from django.views.decorators.http import require_POST

@require_POST
def ai_fix_description(request):
    import json
    try:
        data = json.loads(request.body)
        original = data.get('description', '').strip()
        if not original:
            return JsonResponse({'error': 'No description provided'}, status=400)

        client = _get_nvidia_client()
        response = client.chat.completions.create(
            model="z-ai/glm-5.2",
            messages=[
                {"role": "system", "content": (
                    "You improve rental listing descriptions for a Kenyan property site. "
                    "Fix grammar and clarity, keep it honest and factual, don't invent details "
                    "that weren't mentioned, keep it concise (under 100 words), and keep a friendly, "
                    "professional tone suited to Kenyan renters."
                )},
                {"role": "user", "content": f"Improve this listing description:\n\n{original}"},
            ],
            temperature=0.4,
            max_tokens=200,
        )
        return JsonResponse({'improved': response.choices[0].message.content.strip()})
    except Exception as e:
        print("AI DESCRIPTION FIX ERROR:", e)
        return JsonResponse({'error': 'Something went wrong. Please try again.'}, status=500)
def home(request):
    residences = Residence.objects.filter(approved=True, is_hidden=False)

    county = request.GET.get('county')
    town = request.GET.get('town')

    if county:
        residences = residences.filter(county__icontains=county)
    if town:
        residences = residences.filter(town__icontains=town)

    # Premium listings appear first, then by views
    popular_residences = Residence.objects.filter(
        approved=True, is_hidden=False
    ).order_by('-is_premium', '-views_count')[:12]

    context = {
        'residences': residences,
        'popular_residences': popular_residences,
        'selected_county': county,
        'selected_town': town,
        
    }
    return render(request, 'core/home.html', context)


def about(request):
    form = ContactForm()   

    if request.method == 'POST':
        form = ContactForm(request.POST)
        
        if not check_submission_rate_limit(request, 'contact'):
            messages.error(request, 'Too many messages sent. Please try again in an hour.')
            return redirect('about')

        if form.is_valid():
            send_mail(
                subject=form.cleaned_data['subject'],
                message=f"""
From: {form.cleaned_data['name']}
Email: {form.cleaned_data['email']}

Message:
{form.cleaned_data['message']}
                """,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['homefinder.ke.help@gmail.com'],
                fail_silently=True,
            )
            messages.success(request, 'Your message has been sent successfully.')
            return redirect('about')

    return render(request, 'core/about.html', {'form': form})

def search(request):
    residences = Residence.objects.filter(approved=True, is_hidden=False).order_by('-is_premium', '-created_at')

    q          = request.GET.get('q')
    county     = request.GET.get('county')
    town       = request.GET.get('town')
    house_type = request.GET.get('house_type')
    min_rent   = request.GET.get('min_rent')
    max_rent   = request.GET.get('max_rent')
    water      = request.GET.get('water')
    fibre      = request.GET.get('fibre')
    gated      = request.GET.get('gated')

    if q:
        residences = residences.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q)
        )
    if water == 'yes':
        residences = residences.filter(water_available=True)
    if fibre == 'yes':
        residences = residences.filter(fibre_available=True)
    if gated == 'yes':
        residences = residences.filter(gated_community=True)
    if county:
        residences = residences.filter(county__icontains=county)
    if town:
        residences = residences.filter(town__icontains=town)
    if house_type:
        residences = residences.filter(house_type=house_type)
    if min_rent:
        residences = residences.filter(rent_price__gte=min_rent)
    if max_rent:
        residences = residences.filter(rent_price__lte=max_rent)

    paginator = Paginator(residences, 9)
    page_obj  = paginator.get_page(request.GET.get('page'))

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        results = [{
            'id': r.id,
            'name': r.name,
            'price': f"{r.rent_price:,.0f}",
            'estate': r.town,
            'county': r.county,
            'lat': r.latitude,
            'lng': r.longitude,
            'image': r.front_image.url if r.front_image else '',
            'url': reverse('residence_detail', args=[r.id]),
        } for r in page_obj]
        return JsonResponse({
            'results': results,
            'count': paginator.count,
            'has_next': page_obj.has_next(),
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        })
    return render(request, 'core/search.html', {'page_obj': page_obj})


def residence_list(request):
    residences = Residence.objects.filter(approved=True, is_hidden=False).order_by('-is_premium', '-created_at')
    paginator  = Paginator(residences, 9)
    page_obj   = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/residence_list.html', {'page_obj': page_obj})


def residence_detail(request, pk):
    # Allow owners to preview their own unapproved residences
    if request.user.is_authenticated:
        residence = get_object_or_404(Residence, pk=pk)
        if not residence.approved and residence.owner != request.user:
            raise Http404
    else:
        residence = get_object_or_404(Residence, pk=pk, approved=True)

    # Only count views for non-owners
    # Only count views for non-owners
    if not request.user.is_authenticated or residence.owner != request.user:
        if request.user.is_authenticated:
            if not residence.viewers.filter(id=request.user.id).exists():
                residence.viewers.add(request.user)
                residence.views_count += 1
                residence.save(update_fields=['views_count'])
            from django.utils import timezone
            view, created = ResidenceView.objects.get_or_create(
                residence=residence, user=request.user,
                defaults={'last_viewed': timezone.now().date()}
            )
            if created or view.last_viewed != timezone.now().date():
                view.last_viewed = timezone.now().date()
                view.save(update_fields=['last_viewed'])
                residence.views_count += 1
                residence.save(update_fields=['views_count'])
        else:
            if not request.session.session_key:
                request.session.create()
            
                            

    # Handle gallery uploads (POST only, no duplicate loop)
    if request.method == 'POST':
        for image in request.FILES.getlist('gallery_images'):
            ResidencePhoto.objects.create(residence=residence, image=watermark_image(image))

    related_residences = Residence.objects.filter(
        approved=True,
        county=residence.county
    ).exclude(pk=residence.pk).order_by('-is_premium', '-views_count')[:4]

    sponsored_movers = list(
        Mover.objects.filter(is_approved=True, is_major_sponsor=True)
        .prefetch_related(
            Prefetch('products', queryset=MoverProduct.objects.filter(is_active=True))
        )
        .order_by('-created_at')[:4]
    )
    regular_movers = list(
        Mover.objects.filter(is_approved=True, is_major_sponsor=False)
        .filter(service_counties__icontains=residence.county)
        .order_by('-created_at')[:5]
    )
    sponsored_vendors = list(
        FurnitureVendor.objects.filter(is_approved=True, is_major_sponsor=True)
        .prefetch_related(
            Prefetch('products', queryset=FurnitureProduct.objects.filter(is_active=True))
        )
        .order_by('-created_at')[:4]
    )
    regular_vendors = list(
        FurnitureVendor.objects.filter(is_approved=True, is_major_sponsor=False)
        .filter(service_counties__icontains=residence.county)
        .order_by('-created_at')[:5]
    )
    movers = sponsored_movers + regular_movers
    vendors = sponsored_vendors + regular_vendors

    share_url = request.build_absolute_uri()
    share_text = f"Check out {residence.name} on HomeFinder Kenya: {share_url}"

    context = {
        'residence': residence,
        'related_residences': related_residences,
        'movers': movers,
        'vendors': vendors,
        'sponsored_movers': sponsored_movers,
        'regular_movers': regular_movers,
        'sponsored_vendors': sponsored_vendors,
        'regular_vendors': regular_vendors,
        'share_url': share_url,
        'share_text': share_text,
    }
    return render(request, 'core/residence_detail.html', context)

@login_required
def check_submission_rate_limit(request, action_name, limit=5, window_seconds=3600):
    from django.core.cache import cache
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
    key = f"rate_limit_{action_name}_{ip}"
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, timeout=window_seconds)
    return True

@login_required
def add_residence(request):
    if request.user.email == 'homefinder.ke.help@gmail.com':
        return redirect('admin_dashboard')
    if not check_not_suspended(request):
        return redirect('home')
    if request.method == 'POST':
        form = ResidenceForm(request.POST, request.FILES)
        if form.is_valid():
            residence = form.save(commit=False)
            duplicate = Residence.objects.filter(
                name__iexact=residence.name,
                county__iexact=residence.county,
                town__iexact=residence.town
            ).exists()
            if duplicate:
                form.add_error(None, "This residence already exists in our directory.")
            else:
                residence.owner = request.user
                residence.approved = False
                if 'front_image' in request.FILES:
                    residence.front_image = watermark_image(request.FILES['front_image'])
                if 'vacancy_poster' in request.FILES:
                    residence.vacancy_poster = watermark_image(request.FILES['vacancy_poster'])

                sub_lat = request.POST.get('submission_latitude')
                sub_lng = request.POST.get('submission_longitude')
                if sub_lat and sub_lng:
                    try:
                        residence.submission_latitude = float(sub_lat)
                        residence.submission_longitude = float(sub_lng)
                    except ValueError:
                        pass

                residence.save()

                for gallery_photo in request.FILES.getlist('gallery_images'):
                    ResidencePhoto.objects.create(residence=residence, image=watermark_image(gallery_photo))
                # ── AI Analysis (non-blocking) ───────────────────────────
                try:
                    is_fraud, reason = _ai_fraud_check(residence)
                    residence.suspected_fraud = is_fraud
                    residence.fraud_reason = reason
                    save_fields = ['suspected_fraud', 'fraud_reason']
                    residence.save(update_fields=save_fields)
                except Exception as ai_err:
                    print("AI ANALYSIS ERROR:", ai_err)
                return render(request, 'core/submission_success.html')
    else:
        form = ResidenceForm()

    return render(request, 'core/add_residence.html', {'form': form})


@login_required
def dashboard(request):
    if request.user.email == 'homefinder.ke.help@gmail.com':
        return redirect('admin_dashboard')
    residences = Residence.objects.filter(owner=request.user)
    return render(request, 'core/dashboard.html', {'residences': residences})


from django.core.exceptions import PermissionDenied

def staff_or_help_admin_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_staff or request.user.email == 'homefinder.ke.help@gmail.com':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

@staff_or_help_admin_required
def suspicious_users(request):
    from .user_behavior import get_flagged_users, ai_explain_pattern

    flagged = get_flagged_users()
    for entry in flagged:
        entry['explanation'] = ai_explain_pattern(entry['user'], entry['stats'])

    return render(request, 'core/suspicious_users.html', {'flagged': flagged})

@staff_or_help_admin_required
def admin_dashboard(request):
    from datetime import timedelta
    from django.db.models import Count, Q
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Combine several counts on the same model into ONE query using conditional aggregation
    residence_stats = Residence.objects.aggregate(
        total_views=Sum('views_count'),
        approved_count=Count('id', filter=Q(approved=True)),
        pending_count=Count('id', filter=Q(approved=False, is_hidden=False)),
        premium_count=Count('id', filter=Q(approved=True, is_premium=True)),
        hidden_count=Count('id', filter=Q(is_hidden=True)),
        paused_count=Count('id', filter=Q(is_paused=True)),
        boost_requests_count=Count('id', filter=Q(boost_requested=True, is_premium=False)),
        new_this_week=Count('id', filter=Q(approved=True, created_at__gte=week_ago)),
        new_this_month=Count('id', filter=Q(approved=True, created_at__gte=month_ago)),
    )

    # Annotate viewer counts directly on the querysets, so the template doesn't
    # run a separate query per card for residence.viewers.count()
    pending_residences  = Residence.objects.filter(approved=False, is_hidden=False).annotate(viewer_count=Count('viewers'))
    approved_residences = Residence.objects.filter(approved=True).annotate(viewer_count=Count('viewers'))
    premium_residences  = Residence.objects.filter(approved=True, is_premium=True)
    boost_requests      = Residence.objects.filter(boost_requested=True, is_premium=False)

    total_users = User.objects.count()
    reports = ResidenceReport.objects.filter(reviewed=False).order_by('-created_at')
    user_reports = UserReport.objects.filter(reviewed=False).order_by('-created_at')

    from .models import Favorite
    favorite_stats = Favorite.objects.aggregate(
        total_favorites=Count('id'),
        favorites_this_week=Count('id', filter=Q(created_at__gte=week_ago)),
        favorites_this_month=Count('id', filter=Q(created_at__gte=month_ago)),
    )

    top_residences = Residence.objects.filter(approved=True).order_by('-views_count')[:5]
    all_users = User.objects.all().order_by('-date_joined')[:100]

    context = {
        'pending_residences':   pending_residences,
        'approved_residences':  approved_residences,
        'approved_count':       residence_stats['approved_count'],
        'pending_count':        residence_stats['pending_count'],
        'total_users':          total_users,
        'reports':              reports,
        'user_reports':         user_reports,
        'total_views':          residence_stats['total_views'] or 0,
        'premium_residences':   premium_residences,
        'premium_count':        residence_stats['premium_count'],
        'hidden_count':         residence_stats['hidden_count'],
        'paused_count':         residence_stats['paused_count'],
        'boost_requests':       boost_requests,
        'boost_requests_count': residence_stats['boost_requests_count'],
        'new_this_week':        residence_stats['new_this_week'],
        'new_this_month':       residence_stats['new_this_month'],
        'total_favorites':      favorite_stats['total_favorites'],
        'favorites_this_week':  favorite_stats['favorites_this_week'],
        'favorites_this_month': favorite_stats['favorites_this_month'],
        'top_residences':       top_residences,
        'all_users':            all_users,
    }
    return render(request, 'core/admin_dashboard.html', context)


@staff_or_help_admin_required
def toggle_premium(request, pk):
    residence = get_object_or_404(Residence, pk=pk)
    residence.is_premium = not residence.is_premium
    if residence.is_premium:
        residence.boost_requested = False  # clear request once granted
    residence.save(update_fields=['is_premium', 'boost_requested'])
    # Notify owner
    status = 'granted ⭐ Premium status' if residence.is_premium else 'removed Premium status from'
    Notification.objects.create(
        user=residence.owner,
        message=f'🌟 Admin has {status} your listing "{residence.name}".'
    )
    messages.success(request, f'Premium status toggled for "{residence.name}".')
    return redirect('admin_dashboard')


@staff_or_help_admin_required
def toggle_hide(request, pk):
    residence = get_object_or_404(Residence, pk=pk)
    residence.is_hidden = not residence.is_hidden
    residence.save(update_fields=['is_hidden'])
    state = 'hidden' if residence.is_hidden else 'visible'
    messages.success(request, f'"{residence.name}" is now {state}.')
    return redirect('admin_dashboard')


@staff_or_help_admin_required
def toggle_pause(request, pk):
    residence = get_object_or_404(Residence, pk=pk)
    residence.is_paused = not residence.is_paused
    residence.save(update_fields=['is_paused'])
    state = 'paused' if residence.is_paused else 'active'
    messages.success(request, f'"{residence.name}" is now {state}.')
    return redirect('admin_dashboard')


@login_required
def request_boost(request, pk):
    residence = get_object_or_404(Residence, pk=pk, owner=request.user)
    if not residence.boost_requested and not residence.is_premium:
        residence.boost_requested = True
        residence.save(update_fields=['boost_requested'])
        # Notify all admins
        admins = User.objects.filter(is_staff=True)
        for admin in admins:
            Notification.objects.create(
                user=admin,
                message=f'🚀 Boost request: "{residence.name}" by {request.user.username} wants Premium listing.'
            )
        messages.success(request, 'Boost request sent! Admin will review soon.')
    else:
        messages.info(request, 'This listing already has Premium or a pending request.')
    return redirect('dashboard')


@login_required
def my_favorites(request):
    favorites = Favorite.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/my_favorites.html', {'favorites': favorites})


@login_required
def remove_favorite(request, pk):
    favorite = get_object_or_404(Favorite, pk=pk, user=request.user)
    favorite.delete()
    messages.success(request, 'Removed from favorites.')
    return redirect('my_favorites')


@staff_or_help_admin_required
def approve_residence(request, pk):
    residence = get_object_or_404(Residence, pk=pk)
    residence.approved = True
    residence.save()

    for saved_search in SavedSearch.objects.filter(is_active=True):
        if saved_search.matches(residence):
            Notification.objects.create(
                user=saved_search.user,
                message=f"New listing matches your saved search: {residence.name} in {residence.town}, {residence.county} — KSh {residence.rent_price:,.0f}/month."
            )

    if residence.owner and residence.owner.email:
        try:
            send_mail(
                subject='Your Property Has Been Approved!',
                message=(
                    f'Hello {residence.owner.username},\n\n'
                    f'Good news! Your property:\n\n'
                    f'"{residence.name}"\n\n'
                    f'has been approved and is now live on HomeFinder KE.\n\n'
                    f'You can now receive views, reviews, and inquiries from tenants.\n\n'
                    f'Thank you for using HomeFinder KE.\n\n'
                    f'Best regards,\nHomeFinder KE Team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[residence.owner.email],
                fail_silently=False
            )
        except Exception as e:
            print("APPROVAL EMAIL ERROR:", e)

    messages.success(request, 'Residence approved successfully.')
    return redirect('admin_dashboard')


def check_not_suspended(request):
    """Returns True if the user is allowed to act, False (with message set) if suspended."""
    if request.user.is_authenticated and getattr(request.user.profile, 'is_suspended', False):
        messages.error(request, 'Your account is restricted. Contact support for help.')
        return False
    return True
def reject_residence(request, pk):
    residence = get_object_or_404(Residence, pk=pk)
    residence.delete()
    return redirect('admin_dashboard')


@login_required
def report_residence(request, pk):
    residence = get_object_or_404(Residence, pk=pk, approved=True)

    existing_report = ResidenceReport.objects.filter(
        residence=residence, reported_by=request.user
    ).exists()

    if existing_report:
        return redirect('residence_detail', pk=residence.pk)

    if request.method == 'POST':
        form = ResidenceReportForm(request.POST)

        if not check_submission_rate_limit(request, 'report_residence'):
            messages.error(request, 'Too many reports submitted. Please try again in an hour.')
            return redirect('residence_detail', pk=residence.pk)
        
        if form.is_valid():
            report = form.save(commit=False)
            report.residence   = residence
            report.reported_by = request.user
            report.save()
            return redirect('residence_detail', pk=residence.pk)
    else:
        form = ResidenceReportForm()

    return render(request, 'core/report_residence.html', {'form': form, 'residence': residence})


@staff_or_help_admin_required
def review_report(request, pk):
    report = get_object_or_404(ResidenceReport, pk=pk)
    report.reviewed = True
    report.save()
    return redirect('admin_dashboard')

@staff_or_help_admin_required
def warn_user(request, user_id):
    from django.core.mail import send_mail
    user = get_object_or_404(User, pk=user_id)
    if not user.email:
        messages.error(request, f'{user.username} has no email on file — warning not sent.')
        return redirect('admin_dashboard')
    try:
        send_mail(
            subject='Warning from HomeFinder KE',
            message='Your account has received a warning for violating our community guidelines. Repeated violations may result in suspension.',
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )
        messages.warning(request, f'Warning email actually sent to {user.username} ({user.email}).')
    except Exception as e:
        print("WARN USER EMAIL ERROR:", e)
        messages.error(request, f'Could not send warning to {user.username} — email failed: {e}')
    return redirect('admin_dashboard')

@staff_or_help_admin_required
def review_user_report(request, pk):
    report = get_object_or_404(UserReport, pk=pk)
    report.reviewed = True
    report.save()
    return redirect('admin_dashboard')
@staff_or_help_admin_required
def review_user_report(request, pk):
    report = get_object_or_404(UserReport, pk=pk)
    report.reviewed = True
    report.save()
    return redirect('admin_dashboard')


@staff_or_help_admin_required
def suspend_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.profile.is_suspended = True
    user.profile.save()
    messages.success(request, f'{user.username} has been suspended.')
    return redirect('admin_dashboard')

@staff_or_help_admin_required
def suspended_users(request):
    suspended = Profile.objects.filter(is_suspended=True).select_related('user')
    return render(request, 'suspended_accounts.html', {'suspended': suspended})
@login_required
def save_favorite(request, pk):
    residence = get_object_or_404(Residence, pk=pk, approved=True)
    favorite, created = Favorite.objects.get_or_create(user=request.user, residence=residence)

    if created:
        messages.success(request, 'Residence saved successfully.')
    else:
        messages.info(request, 'Residence is already in your favorites.')

    return redirect('residence_detail', pk=residence.pk)


def owner_profile(request, user_id):
    owner    = get_object_or_404(User, id=user_id)
    residences = Residence.objects.filter(owner=owner, approved=True)
    profile, created = Profile.objects.get_or_create(user=owner)

    context = {
        'owner': owner,
        'profile': profile,
        'residences': residences,
    }
    return render(request, 'core/owner_profile.html', context)

@staff_or_help_admin_required
def suspended_users(request):
    from core.models import Profile
    suspended = Profile.objects.filter(is_suspended=True).select_related('user')
    return render(request, 'core/suspended_users.html', {'suspended': suspended})

@staff_or_help_admin_required
def unsuspend_user(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.profile.is_suspended = False
    user.profile.save()
    messages.success(request, f'{user.username} has been unsuspended and can now list, message, and post again.')
    return redirect('admin_dashboard')

@login_required
def add_review(request, pk):
    residence = get_object_or_404(Residence, pk=pk, approved=True)

    existing_review = Review.objects.filter(residence=residence, user=request.user).exists()
    if existing_review:
        messages.warning(request, 'You have already reviewed this residence.')
        return redirect('residence_detail', pk=residence.pk)


    if residence.owner == request.user:
        messages.warning(request, "You can't review your own listing.")
        return redirect('residence_detail', pk=residence.pk)


    if residence.owner == request.user:
        messages.warning(request, "You can't review your own listing.")
        return redirect('residence_detail', pk=residence.pk)
        

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review           = form.save(commit=False)
            review.residence = residence
            review.user      = request.user
            review.save()
            messages.success(request, 'Review submitted successfully.')
            return redirect('residence_detail', pk=residence.pk)
    else:
        form = ReviewForm()

    return render(request, 'core/add_review.html', {'form': form, 'residence': residence})



@login_required
def edit_residence(request, pk):
    is_admin = request.user.is_staff or request.user.email == 'homefinder.ke.help@gmail.com'
    if is_admin:
        residence = get_object_or_404(Residence, pk=pk)
    else:
        residence = get_object_or_404(Residence, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = ResidenceForm(request.POST, request.FILES, instance=residence)
        if form.is_valid():
            form.save()
            messages.success(request, 'Residence updated successfully.')
            if is_admin and residence.owner != request.user:
                return redirect('admin_dashboard')
            return redirect('residence_detail', pk=residence.pk)
    else:
        form = ResidenceForm(instance=residence)

    return render(request, 'core/edit_residence.html', {'form': form, 'residence': residence})

@login_required
def edit_profile(request):
    profile = request.user.profile

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'core/edit_profile.html', {'form': form})


@login_required
def notifications(request):
    notifications = request.user.notifications.all().order_by('-created_at')
    notifications.update(is_read=True)
    return render(request, 'notifications.html', {'notifications': notifications})


from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied

# This function returns True ONLY if the user is logged in with your specific email
def is_help_admin(user):
    if user.is_authenticated and user.email == 'homefinder.ke.help@gmail.com':
        return True
    raise PermissionDenied # Throws a 403 Forbidden error for anyone else

@login_required
@user_passes_test(is_help_admin)
def admin_dashboard_view(request):
    # Fetch your context stats here
    context = {
        'total_views': 12450,
        'total_users': 340,
        'approved_count': 89,
        'pending_count': 5,
        'pending_residences': [], # Add your querysets here
        'reports': [],
    }
    return render(request, 'admin_dashboard.html', context)

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'admin_dashboard.html'

    # The test that checks the email explicitly
    def test_func(self):
        return self.request.user.email == 'homefinder.ke.help@gmail.com'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Populate your stats for admin_dashboard.html
        context['total_views'] = 12450
        # ... your context logic
        return context
    
@login_required
def compare_residences(request):
    ids = request.GET.get('ids', '')
    id_list = [int(i) for i in ids.split(',') if i.strip().isdigit()][:3]
    residences = Residence.objects.filter(id__in=id_list)
    # preserve the order the user picked them in
    residences = sorted(residences, key=lambda r: id_list.index(r.id))
    return render(request, 'core/compare.html', {'residences': residences})    


from django.http import FileResponse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from .forms import LeaseAgreementForm
from .models import LeaseAgreement


@login_required
def generate_lease(request, pk):
    residence = get_object_or_404(Residence, pk=pk)

    if request.method == 'POST':
        form = LeaseAgreementForm(request.POST)
        if form.is_valid():
            lease = form.save(commit=False)
            lease.residence = residence
            lease.tenant = request.user
            lease.save()
            return redirect('download_lease_pdf', pk=lease.pk)
    else:
        form = LeaseAgreementForm(initial={
            'monthly_rent': residence.rent_price,
            'landlord_full_name': residence.owner.get_full_name() or residence.owner.username if residence.owner else '',
        })

    return render(request, 'core/lease_form.html', {'form': form, 'residence': residence})


@login_required
def download_lease_pdf(request, pk):
    lease = get_object_or_404(LeaseAgreement, pk=pk, tenant=request.user)
    residence = lease.residence

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('LeaseTitle', parent=styles['Heading1'], textColor=colors.HexColor('#0F766E'))
    elements = []

    elements.append(Paragraph("Residential Lease Agreement", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Property: {residence.name}", styles['Normal']))
    elements.append(Paragraph(f"Location: {residence.town}, {residence.county}", styles['Normal']))
    elements.append(Spacer(1, 16))

    data = [
        ['Landlord', lease.landlord_full_name],
        ['Landlord Phone', lease.landlord_phone],
        ['Tenant', lease.tenant_full_name],
        ['Tenant ID Number', lease.tenant_id_number],
        ['Tenant Phone', lease.tenant_phone],
        ['Monthly Rent', f"KSh {lease.monthly_rent:,.0f}"],
        ['Deposit Amount', f"KSh {lease.deposit_amount:,.0f}"],
        ['Lease Start Date', lease.lease_start_date.strftime('%d %B %Y')],
        ['Lease Duration', f"{lease.lease_duration_months} months"],
    ]
    table = Table(data, colWidths=[5*cm, 10*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0FDFA')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#99F6E4')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    terms = (
        "This agreement confirms the tenant's intent to rent the above property under the terms "
        "stated. The tenant agrees to pay rent monthly in advance and maintain the property in "
        "good condition. The deposit is refundable at the end of the tenancy, subject to inspection. "
        "Either party may terminate this agreement with 30 days written notice, unless otherwise agreed."
    )
    elements.append(Paragraph(terms, styles['Normal']))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "Disclaimer: This document is a template generated by HomeFinder Kenya and does not "
        "constitute legal advice. Both parties are encouraged to seek independent legal review "
        "before signing.", ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    ))
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("Landlord Signature: _______________________     Date: ____________", styles['Normal']))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Tenant Signature: _______________________     Date: ____________", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    filename = f"lease_agreement_{residence.id}_{lease.id}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


from .forms import RoommateProfileForm
from .models import RoommateProfile

@login_required
def roommate_list(request):
    profiles = RoommateProfile.objects.filter(is_active=True).exclude(user=request.user)

    county = request.GET.get('county')
    if county:
        profiles = profiles.filter(preferred_county=county)

    my_profile = RoommateProfile.objects.filter(user=request.user).first()
    return render(request, 'core/roommate_list.html', {'profiles': profiles, 'my_profile': my_profile})


@login_required
def roommate_profile_edit(request):
    if not check_not_suspended(request):
        return redirect('roommate_list')
    profile, created = RoommateProfile.objects.get_or_create(user=request.user, defaults={
        'budget_min': 0, 'budget_max': 0, 'preferred_county': 'Nairobi', 'bio': ''
    })
    if request.method == 'POST':
        form = RoommateProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your roommate profile has been saved.')
            return redirect('roommate_list')
    else:
        form = RoommateProfileForm(instance=profile)
    return render(request, 'core/roommate_profile_edit.html', {'form': form})


@login_required
def roommate_deactivate(request):
    RoommateProfile.objects.filter(user=request.user).update(is_active=False)
    messages.info(request, 'Your roommate profile is now hidden from listings.')
    return redirect('roommate_list')

import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .mpesa import initiate_stk_push
from .models import Donation

@require_POST
def donate_stk_push(request):
    try:
        data = json.loads(request.body)
        phone = data.get('phone', '').strip()
        amount = data.get('amount')

        if not phone or not amount or float(amount) < 1:
            return JsonResponse({'error': 'Please enter a valid phone number and amount.'}, status=400)

        donation = Donation.objects.create(phone_number=phone, amount=amount)
        result = initiate_stk_push(phone, amount)

        if result.get('ResponseCode') == '0':
            donation.checkout_request_id = result.get('CheckoutRequestID', '')
            donation.merchant_request_id = result.get('MerchantRequestID', '')
            donation.save()
            return JsonResponse({'message': 'Check your phone and enter your M-Pesa PIN to complete.'})
        else:
            donation.status = 'failed'
            donation.save()
            return JsonResponse({'error': result.get('errorMessage', 'Something went wrong. Try again.')}, status=400)

    except Exception as e:
        print("MPESA ERROR:", e)
        return JsonResponse({'error': 'Something went wrong. Please try again.'}, status=500)


@csrf_exempt
@require_POST
def mpesa_callback(request):
    data = json.loads(request.body)
    result = data.get('Body', {}).get('stkCallback', {})
    checkout_id = result.get('CheckoutRequestID')

    try:
        donation = Donation.objects.get(checkout_request_id=checkout_id)
        if result.get('ResultCode') == 0:
            donation.status = 'success'
            items = result.get('CallbackMetadata', {}).get('Item', [])
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    donation.mpesa_receipt = item.get('Value', '')
            donation.save()
        else:
            donation.status = 'failed'
            donation.save()
    except Donation.DoesNotExist:
        pass

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

from reportlab.platypus import Image as RLImage

@staff_or_help_admin_required
def verify_location(request, pk):
    residence = get_object_or_404(Residence, pk=pk)

    from .amenity_check import check_nearby_amenities
    import requests
    from math import radians, sin, cos, sqrt, atan2

    def haversine_km(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return round(6371 * 2 * atan2(sqrt(a), sqrt(1 - a)), 2)

    # ── Geocode the claimed town/county to find where it should actually be ──
    geocode_result = None
    town_county_distance_km = None
    if residence.town or residence.county:
        try:
            query = f"{residence.town}, {residence.county}, Kenya"
            resp = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'q': query, 'format': 'json', 'limit': 1},
                headers={'User-Agent': 'HomeFinderKE/1.0 (homefinder.ke.help@gmail.com)'},
                timeout=10,
            )
            data = resp.json()
            if data:
                geocode_result = {
                    'lat': float(data[0]['lat']),
                    'lng': float(data[0]['lon']),
                    'display_name': data[0].get('display_name', query),
                }
                if residence.latitude and residence.longitude:
                    town_county_distance_km = haversine_km(
                        residence.latitude, residence.longitude,
                        geocode_result['lat'], geocode_result['lng']
                    )
        except Exception as e:
            print("GEOCODE CHECK ERROR:", e)

    # ── GPS-snapshot vs claimed (existing check) ──
    distance_km = None
    if (residence.latitude and residence.longitude and
            residence.submission_latitude and residence.submission_longitude):
        distance_km = haversine_km(
            residence.latitude, residence.longitude,
            residence.submission_latitude, residence.submission_longitude
        )

    # ── Amenities checked against the CLAIMED coordinates specifically ──
    amenity_result = check_nearby_amenities(
        residence.latitude,
        residence.longitude,
        residence.nearby_school,
        residence.nearby_hospital,
        residence.nearest_stage,
    )

    return render(request, 'core/verify_location.html', {
        'residence': residence,
        'distance_km': distance_km,
        'amenity_result': amenity_result,
        'geocode_result': geocode_result,
        'town_county_distance_km': town_county_distance_km,
    })




def download_residence_pdf(request, pk):
    residence = get_object_or_404(Residence, pk=pk, approved=True)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ResTitle', parent=styles['Heading1'], textColor=colors.HexColor('#0F766E'))
    section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=13,
                                    textColor=colors.HexColor('#0F766E'), spaceBefore=16, spaceAfter=8)
    label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9,
                                  textColor=colors.HexColor('#5EAFA8'), spaceAfter=2)
    elements = []

    # ── Header ──
    elements.append(Paragraph(residence.name, title_style))
    elements.append(Paragraph(f"{residence.town}, {residence.county}", styles['Normal']))
    elements.append(Spacer(1, 14))

    if residence.front_image:
        try:
            img = RLImage(residence.front_image.path, width=16*cm, height=10*cm)
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 16))
        except Exception:
            pass

    # ── Core details ──
    data = [
        ['Monthly Rent', f"KSh {residence.rent_price:,.0f}" if residence.rent_price else 'N/A'],
        ['Deposit', f"KSh {residence.deposit_amount:,.0f}" if residence.deposit_amount else 'N/A'],
        ['House Type', residence.get_house_type_display() if residence.house_type else 'N/A'],
        ['Landmark', residence.landmark or '—'],
        ['Nearest Stage', residence.nearest_stage or '—'],
        ['Nearby School', residence.nearby_school or '—'],
        ['Nearby Hospital', residence.nearby_hospital or '—'],
    ]
    table = Table(data, colWidths=[5*cm, 11*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0FDFA')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#99F6E4')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 18))

    # ── Amenities ──
    amenities = []
    if residence.water_available: amenities.append('Water Available')
    if residence.fibre_available: amenities.append('Fibre Internet')
    if residence.gated_community: amenities.append('Gated Community')
    if residence.cctv_available: amenities.append('CCTV')
    if residence.security_guard: amenities.append('Security Guard')
    if amenities:
        elements.append(Paragraph("Amenities", label_style))
        elements.append(Paragraph(" &nbsp;·&nbsp; ".join(amenities), styles['Normal']))
        elements.append(Spacer(1, 16))

    if residence.description:
        elements.append(Paragraph("Description", label_style))
        elements.append(Paragraph(residence.description, styles['Normal']))
        elements.append(Spacer(1, 16))

    # ── Sponsored Movers & Vendors ──
    sponsored_movers = Mover.objects.filter(is_approved=True, is_major_sponsor=True)[:4]
    sponsored_vendors = FurnitureVendor.objects.filter(is_approved=True, is_major_sponsor=True)[:4]

    if sponsored_movers or sponsored_vendors:
        elements.append(Paragraph("Recommended Movers & Furniture Vendors", section_style))

    def render_partner_row(partner, logo_attr='logo'):
        row_elements = []
        logo_field = getattr(partner, logo_attr, None)
        try:
            if logo_field and hasattr(logo_field, 'path'):
                thumb = RLImage(logo_field.path, width=2.2*cm, height=2.2*cm)
            else:
                thumb = None
        except Exception:
            thumb = None
        name_cell = Paragraph(
            f"<b>{partner.name}</b><br/><font size=8 color='#5EAFA8'>{partner.phone_number}</font>",
            styles['Normal']
        )
        return [thumb, name_cell]

    if sponsored_movers:
        elements.append(Paragraph("Movers", label_style))
        rows = [render_partner_row(m) for m in sponsored_movers]
        t = Table(rows, colWidths=[2.5*cm, 13.5*cm])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10))

    if sponsored_vendors:
        elements.append(Paragraph("Furniture Vendors", label_style))
        rows = [render_partner_row(v, logo_attr='image') for v in sponsored_vendors]
        t = Table(rows, colWidths=[2.5*cm, 13.5*cm])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 16))

    # ── Footer ──
    elements.append(Paragraph(
        f"Generated by HomeFinder Kenya on {timezone.now().strftime('%d %B %Y')}. "
        f"View this listing online for the most up-to-date information and photos.",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    ))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"{residence.name.replace(' ', '_')}_HomeFinderKE.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Length'] = len(pdf_bytes)
    return response

@require_POST
@login_required
def ai_improve_description(request):
    return JsonResponse({'error': 'AI features are currently offline for maintenance.'}, status=503)


def ai_recommendations(request):
    return JsonResponse({'recommendations': []})



@staff_or_help_admin_required
def residence_viewers(request, pk):
    residence = get_object_or_404(Residence, pk=pk)
    viewers = residence.viewers.all().order_by('username')
    return render(request, 'core/residence_viewers.html', {
        'residence': residence,
        'viewers': viewers,
    })
@staff_or_help_admin_required
def add_mover(request):
    if request.method == 'POST':
        form = MoverForm(request.POST, request.FILES)
        if form.is_valid():
            mover = form.save(commit=False)
            mover.is_approved = True
            mover.is_major_sponsor = False
            mover.save()
            for photo in request.FILES.getlist('gallery_images'):
                MoverGalleryImage.objects.create(mover=mover, image=photo)
            messages.success(request, f'Mover "{mover.name}" has been added successfully.')
            return redirect('admin_dashboard')
    else:
        form = MoverForm()
    return render(request, 'core/add_mover.html', {'form': form})


@staff_or_help_admin_required
def add_mover_sponsor(request):
    if request.method == 'POST':
        form = MoverSponsorForm(request.POST, request.FILES)
        if form.is_valid():
            mover = form.save(commit=False)
            mover.is_approved = True
            mover.is_major_sponsor = True
            mover.save()
            for photo in request.FILES.getlist('gallery_images'):
                MoverGalleryImage.objects.create(mover=mover, image=photo)
            messages.success(request, f'Sponsored mover "{mover.name}" has been added successfully.')
            return redirect('admin_dashboard')
    else:
        form = MoverSponsorForm()
    return render(request, 'core/add_mover_sponsor.html', {'form': form})


@staff_or_help_admin_required
def add_furniture_vendor(request):
    if request.method == 'POST':
        form = FurnitureVendorForm(request.POST, request.FILES)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.is_approved = True
            vendor.is_major_sponsor = False
            vendor.save()
            for photo in request.FILES.getlist('gallery_images'):
                FurnitureGalleryImage.objects.create(vendor=vendor, image=photo)
            messages.success(request, f'Furniture Vendor "{vendor.name}" has been added successfully.')
            return redirect('admin_dashboard')
    else:
        form = FurnitureVendorForm()
    return render(request, 'core/add_furniture_vendor.html', {'form': form})


@staff_or_help_admin_required
def add_furniture_vendor_sponsor(request):
    if request.method == 'POST':
        form = FurnitureVendorSponsorForm(request.POST, request.FILES)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.is_approved = True
            vendor.is_major_sponsor = True
            vendor.save()
            messages.success(request, f'Sponsored furniture vendor "{vendor.name}" has been added successfully.')
            return redirect('admin_dashboard')
    else:
        form = FurnitureVendorSponsorForm()
    return render(request, 'core/add_furniture_vendor_sponsor.html', {'form': form})

@staff_or_help_admin_required
def edit_mover(request, pk):
    mover = get_object_or_404(Mover, pk=pk)
    if request.method == 'POST':
        form = (MoverSponsorForm if mover.is_major_sponsor else MoverForm)(request.POST, request.FILES, instance=mover)
        if form.is_valid():
            form.save()
            messages.success(request, f'Mover "{mover.name}" updated.')
            return redirect('vendor_dashboard')
    else:
        form = (MoverSponsorForm if mover.is_major_sponsor else MoverForm)(instance=mover)
    return render(request, 'core/edit_mover.html', {'form': form, 'mover': mover})


@staff_or_help_admin_required
def delete_mover(request, pk):
    mover = get_object_or_404(Mover, pk=pk)
    name = mover.name
    mover.delete()
    messages.success(request, f'Mover "{name}" removed.')
    return redirect('vendor_dashboard')


@staff_or_help_admin_required
def edit_furniture_vendor(request, pk):
    vendor = get_object_or_404(FurnitureVendor, pk=pk)
    if request.method == 'POST':
        form = (FurnitureVendorSponsorForm if vendor.is_major_sponsor else FurnitureVendorForm)(request.POST, request.FILES, instance=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Furniture vendor "{vendor.name}" updated.')
            return redirect('vendor_dashboard')
    else:
        form = (FurnitureVendorSponsorForm if vendor.is_major_sponsor else FurnitureVendorForm)(instance=vendor)
    return render(request, 'core/edit_furniture_vendor.html', {'form': form, 'vendor': vendor})


@staff_or_help_admin_required
def delete_furniture_vendor(request, pk):
    vendor = get_object_or_404(FurnitureVendor, pk=pk)
    name = vendor.name
    vendor.delete()
    messages.success(request, f'Furniture vendor "{name}" removed.')
    return redirect('vendor_dashboard')


@staff_or_help_admin_required
def remove_expired_vendors(request):
    """Deletes any Mover/FurnitureVendor whose contract_end_date has passed.
    Ones with no contract_end_date set are left alone — only explicit expiries are removed."""
    today = timezone.now().date()
    expired_movers = Mover.objects.filter(contract_end_date__lt=today)
    expired_vendors = FurnitureVendor.objects.filter(contract_end_date__lt=today)
    count = expired_movers.count() + expired_vendors.count()
    expired_movers.delete()
    expired_vendors.delete()
    messages.success(request, f'Removed {count} expired contract(s).')
    return redirect('vendor_dashboard')

def mover_detail(request, pk):
    mover = get_object_or_404(Mover, pk=pk, is_approved=True)
    return render(request, 'core/mover_detail.html', {'mover': mover})

def furniture_vendor_detail(request, pk):
    vendor = get_object_or_404(FurnitureVendor, pk=pk, is_approved=True)
    return render(request, 'core/furniture_vendor_detail.html', {'vendor': vendor})

def robots_txt(request):
    base_url = request.build_absolute_uri('/')[:-1]
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /control-panel-2947/\n"
        "Disallow: /accounts/\n"
        "Disallow: /chat/\n"
        "Disallow: /dashboard/\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )
    return HttpResponse(content, content_type="text/plain")


def sitemap_xml(request):
    base_url = request.build_absolute_uri('/')[:-1]
    
    # Static key pages
    pages = [
        {'loc': f"{base_url}/", 'changefreq': 'daily', 'priority': '1.0'},
        {'loc': f"{base_url}/about/", 'changefreq': 'weekly', 'priority': '0.7'},
        {'loc': f"{base_url}/residences/", 'changefreq': 'daily', 'priority': '0.9'},
        {'loc': f"{base_url}/roommates/", 'changefreq': 'daily', 'priority': '0.8'},
        {'loc': f"{base_url}/privacy-policy/", 'changefreq': 'monthly', 'priority': '0.3'},
        {'loc': f"{base_url}/terms-of-service/", 'changefreq': 'monthly', 'priority': '0.3'},
    ]
    
    # Dynamic residence detail pages (approved listings)
    residences = Residence.objects.filter(approved=True).order_by('-id')
    for r in residences:
        lastmod = r.created_at.strftime('%Y-%m-%d') if r.created_at else None
        page = {
            'loc': f"{base_url}/residences/{r.pk}/",
            'changefreq': 'weekly',
            'priority': '0.8'
        }
        if lastmod:
            page['lastmod'] = lastmod
        pages.append(page)
        
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        xml_content += '  <url>\n'
        xml_content += f"    <loc>{page['loc']}</loc>\n"
        if 'lastmod' in page:
            xml_content += f"    <lastmod>{page['lastmod']}</lastmod>\n"
        xml_content += f"    <changefreq>{page['changefreq']}</changefreq>\n"
        xml_content += f"    <priority>{page['priority']}</priority>\n"
        xml_content += '  </url>\n'
    xml_content += '</urlset>\n'
    
    return HttpResponse(xml_content, content_type='application/xml')

import os
from intasend import APIService

@require_POST
def initiate_donation(request):
    try:
        data = json.loads(request.body)
        phone = data.get('phone', '').strip()
        amount = data.get('amount')

        if not phone or not amount or float(amount) < 1:
            return JsonResponse({'success': False, 'error': 'Please enter a valid phone number and amount.'}, status=400)

        # Ensure phone is in standard 254 format for IntaSend
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('+254'):
            phone = phone[1:]

        # IntaSend SDK Initialization
        secret_token = os.getenv('INTASEND_SECRET_TOKEN')
        publishable_key = os.getenv('INTASEND_PUBLISHABLE_KEY')

        if not secret_token or not publishable_key:
            return JsonResponse({'success': False, 'error': 'Payment gateway keys missing.'}, status=500)

        service = APIService(token=secret_token, publishable_key=publishable_key, test=False)

        # Execute M-Pesa STK Push
        response = service.collect.mpesa_stk_push(
            phone_number=phone,
            email="homefinder.ke.help@gmail.com",
            amount=float(amount),
            narrative="HomeFinder Support Donation"
        )
        
        return JsonResponse({'success': True, 'message': 'Prompt sent to your phone! Please complete the payment.'})

    except Exception as e:
        print("INTASEND ERROR:", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

from .forms import UserReportForm
from .models import UserReport

@login_required
def report_user(request, user_id):
    reported_user = get_object_or_404(User, pk=user_id)

    if reported_user == request.user:
        messages.error(request, "You can't report yourself.")
        return redirect('home')

    if request.method == 'POST':
        form = UserReportForm(request.POST)

        if not check_submission_rate_limit(request, 'report_user'):
            messages.error(request, 'Too many reports submitted. Please try again in an hour.')
            return redirect('home')

        if form.is_valid():
            report = form.save(commit=False)
            report.reported_user = reported_user
            report.reported_by = request.user
            report.save()
            messages.success(request, 'Thank you — your report has been submitted for review.')
            return redirect('home')
    else:
        form = UserReportForm()

    return render(request, 'core/report_user.html', {'form': form, 'reported_user': reported_user})

from .models import SavedSearch

@login_required
def save_search(request):
    if request.method == 'POST':
        SavedSearch.objects.create(
            user=request.user,
            keyword=request.POST.get('q', ''),
            county=request.POST.get('county', ''),
            town=request.POST.get('town', ''),
            house_type=request.POST.get('house_type', ''),
            min_rent=request.POST.get('min_rent') or None,
            max_rent=request.POST.get('max_rent') or None,
        )
        messages.success(request, "Search saved! We'll notify you when a matching listing appears.")
    return redirect('search')


@login_required
def my_saved_searches(request):
    searches = SavedSearch.objects.filter(user=request.user)
    return render(request, 'core/saved_searches.html', {'searches': searches})


@login_required
def delete_saved_search(request, pk):
    SavedSearch.objects.filter(pk=pk, user=request.user).delete()
    messages.info(request, 'Saved search removed.')
    return redirect('my_saved_searches')

def activity_feed(request):
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Count

    cutoff = timezone.now() - timedelta(days=7)

    new_listings = Residence.objects.filter(
        approved=True, created_at__gte=cutoff
    ).order_by('-created_at')[:15]

    new_roommates = RoommateProfile.objects.filter(
        is_active=True, created_at__gte=cutoff
    ).order_by('-created_at')[:15]

    trending = Residence.objects.filter(
        approved=True
    ).annotate(
        recent_views=Count('viewers')
    ).order_by('-recent_views')[:10]

    events = []
    for r in new_listings:
        events.append({'type': 'new_listing', 'time': r.created_at, 'residence': r})
    for rp in new_roommates:
        events.append({'type': 'new_roommate', 'time': rp.created_at, 'town': rp.preferred_town or rp.preferred_county})
    for r in trending:
        if r.recent_views >= 3:
            events.append({'type': 'trending', 'time': r.created_at, 'residence': r, 'views': r.recent_views})

    events.sort(key=lambda e: e['time'], reverse=True)

    return render(request, 'core/activity_feed.html', {'events': events[:30]})


import csv

@staff_or_help_admin_required
def export_residences_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="homefinder_listings.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Name', 'Owner', 'County', 'Town', 'House Type', 'Rent', 'Deposit',
                      'Approved', 'Premium', 'Views', 'Phone', 'Created At'])

    for r in Residence.objects.all().select_related('owner'):
        writer.writerow([
            r.id, r.name, r.owner.username if r.owner else '', r.county, r.town,
            r.get_house_type_display(), r.rent_price, r.deposit_amount,
            r.approved, r.is_premium, r.views_count, r.phone_number, r.created_at,
        ])

    return response

@staff_or_help_admin_required
def vendor_dashboard(request):
    """
    Shows all Movers and FurnitureVendors with scrape status and contract
    expiry — lets a staff account or the help-admin account spot failed
    scrapes, edit listings, and remove expired ones.
    """
    from django.utils import timezone
    today = timezone.now().date()

    movers = Mover.objects.all().order_by('-is_major_sponsor', 'name')
    furniture_vendors = FurnitureVendor.objects.all().order_by('-is_major_sponsor', 'name')

    failed_count = (
        movers.filter(scrape_status='failed').count()
        + furniture_vendors.filter(scrape_status='failed').count()
    )
    expired_count = (
        movers.filter(contract_expires_at__lt=today).count()
        + furniture_vendors.filter(contract_expires_at__lt=today).count()
    )

    context = {
        'movers': movers,
        'furniture_vendors': furniture_vendors,
        'failed_count': failed_count,
        'expired_count': expired_count,
        'today': today,
    }
    return render(request, 'core/vendor_dashboard.html', context)


@staff_or_help_admin_required
def edit_mover(request, pk):
    mover = get_object_or_404(Mover, pk=pk)
    FormClass = MoverSponsorForm if mover.is_major_sponsor else MoverForm
    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=mover)
        if form.is_valid():
            form.save()
            expires_at = request.POST.get('contract_expires_at')
            if expires_at:
                mover.contract_expires_at = expires_at
                mover.save(update_fields=['contract_expires_at'])
            for photo in request.FILES.getlist('gallery_images'):
                MoverGalleryImage.objects.create(mover=mover, image=photo)
            messages.success(request, f'Mover "{mover.name}" updated.')
            return redirect('vendor_dashboard')
    else:
        form = FormClass(instance=mover)
    return render(request, 'core/edit_mover.html', {'form': form, 'mover': mover})


@staff_or_help_admin_required
def delete_mover(request, pk):
    mover = get_object_or_404(Mover, pk=pk)
    if request.method == 'POST':
        name = mover.name
        mover.delete()
        messages.success(request, f'Mover "{name}" removed.')
        return redirect('vendor_dashboard')
    return render(request, 'core/confirm_delete.html', {'object': mover, 'object_type': 'Mover'})


@staff_or_help_admin_required
def edit_furniture_vendor(request, pk):
    vendor = get_object_or_404(FurnitureVendor, pk=pk)
    FormClass = FurnitureVendorSponsorForm if vendor.is_major_sponsor else FurnitureVendorForm
    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=vendor)
        if form.is_valid():
            form.save()
            expires_at = request.POST.get('contract_expires_at')
            if expires_at:
                vendor.contract_expires_at = expires_at
                vendor.save(update_fields=['contract_expires_at'])
            for photo in request.FILES.getlist('gallery_images'):
                FurnitureGalleryImage.objects.create(vendor=vendor, image=photo)
            messages.success(request, f'Furniture vendor "{vendor.name}" updated.')
            return redirect('vendor_dashboard')
    else:
        form = FormClass(instance=vendor)
    return render(request, 'core/edit_furniture_vendor.html', {'form': form, 'vendor': vendor})


@staff_or_help_admin_required
def delete_furniture_vendor(request, pk):
    vendor = get_object_or_404(FurnitureVendor, pk=pk)
    if request.method == 'POST':
        name = vendor.name
        vendor.delete()
        messages.success(request, f'Furniture vendor "{name}" removed.')
        return redirect('vendor_dashboard')
    return render(request, 'core/confirm_delete.html', {'object': vendor, 'object_type': 'FurnitureVendor'})


@staff_or_help_admin_required
def remove_expired_vendors(request):
    """One-click cleanup: deletes every Mover/FurnitureVendor whose contract has expired."""
    from django.utils import timezone
    today = timezone.now().date()
    if request.method == 'POST':
        expired_movers = Mover.objects.filter(contract_expires_at__lt=today)
        expired_vendors = FurnitureVendor.objects.filter(contract_expires_at__lt=today)
        count = expired_movers.count() + expired_vendors.count()
        expired_movers.delete()
        expired_vendors.delete()
        messages.success(request, f'Removed {count} expired vendor listing(s).')
    return redirect('vendor_dashboard')
    """
    Shows all Movers and FurnitureVendors with their scrape status — lets a
    staff account or the help-admin account spot failed scrapes and manually
    update products for them.
    """
    movers = Mover.objects.all().order_by('-is_major_sponsor', 'name')
    furniture_vendors = FurnitureVendor.objects.all().order_by('-is_major_sponsor', 'name')

    failed_count = (
        movers.filter(scrape_status='failed').count()
        + furniture_vendors.filter(scrape_status='failed').count()
    )

    context = {
        'movers': movers,
        'furniture_vendors': furniture_vendors,
        'failed_count': failed_count,
    }
    return render(request, 'core/vendor_dashboard.html', context)

@staff_or_help_admin_required
def vendor_dashboard(request):
    """
    Shows all Movers and FurnitureVendors with their scrape status, lets a
    staff account or help-admin edit/remove them, and flags expired contracts.
    """
    today = timezone.now().date()
    movers = Mover.objects.all().order_by('-is_major_sponsor', 'name')
    furniture_vendors = FurnitureVendor.objects.all().order_by('-is_major_sponsor', 'name')

    failed_count = (
        movers.filter(scrape_status='failed').count()
        + furniture_vendors.filter(scrape_status='failed').count()
    )
    expired_count = (
        movers.filter(contract_end_date__lt=today).count()
        + furniture_vendors.filter(contract_end_date__lt=today).count()
    )

    context = {
        'movers': movers,
        'furniture_vendors': furniture_vendors,
        'failed_count': failed_count,
        'expired_count': expired_count,
        'today': today,
    }
    return render(request, 'core/vendor_dashboard.html', context)