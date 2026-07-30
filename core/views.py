from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import Http404, HttpResponse
from .models import Residence, ResidenceReport, UserReport
from .models import Residence, ResidenceReport, ResidenceView
from .forms import ResidenceForm, ResidenceReportForm, MoverForm, FurnitureVendorForm, MoverSponsorForm, FurnitureVendorSponsorForm
from django.contrib import messages
from django.db.models import Count
from django.db.models import Prefetch, Count
from .models import Residence, ResidenceReport, Favorite
from django.db.models import Sum
from django.db.models import Prefetch, Count, Avg
from django.contrib import messages
import math
from django.contrib.auth.models import User
from .models import Review
from .forms import ReviewForm
from django.db.models import Sum, Prefetch
from django.core.paginator import Paginator
from .forms import ProfileForm, SettingsUserForm, SettingsProfileForm, NotificationPreferenceForm, AppearanceForm, PrivacyForm, IDVerificationForm
from .models import Residence, Profile, NotificationPreference, IDVerification
from accounts.models import KnownDevice
from django.contrib.sessions.models import Session
from django.utils import timezone
from allauth.mfa.models import Authenticator
from django.core.mail import send_mail
from django.conf import settings
from .models import ResidencePhoto, Mover, FurnitureVendor, MoverProduct, FurnitureProduct, MoverGalleryImage, FurnitureGalleryImage, MoverFavorite, FurnitureVendorFavorite, MoverReview, FurnitureVendorReview
from business.models import Business
from django.contrib import messages
from .forms import ContactForm
from django.contrib.auth.decorators import login_required
from .models import Notification
from django.db.models import Prefetch, Count, Avg
import math
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from .models import ResidencePhoto, Mover, FurnitureVendor, MoverProduct, FurnitureProduct, MoverGalleryImage, FurnitureGalleryImage, MoverFavorite, FurnitureVendorFavorite, ListingAgreement, CURRENT_TERMS_VERSION, LISTING_TERMS_TEXT
import json
import base64
from openai import OpenAI
from django.views.decorators.http import require_POST
from .watermark import watermark_image
# ─── AI NVIDIA helpers ──────────────────────────────────────────────────────
def _get_nvidia_client():
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=settings.NVIDIA_API_KEY)

def _get_groq_client():
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=settings.GROQ_API_KEY)

# Prompts per upload context — keeps one endpoint reusable everywhere
_IMAGE_CHECK_PROMPTS = {
    'property': (
        "You check property/vacancy photos for a Kenyan rental listing site. Look at this image and judge ALL of: "
        "1) SUBJECT: is it a real photo of a building exterior, compound, room interior, or apartment — "
        "NOT food, furniture close-ups with no room visible, people, vehicles, unrelated objects, memes, or logos? "
        "2) CLARITY: is it sharp enough to show real detail (not blurry, not too dark, not a screenshot)? "
        "3) WATERMARKS: does it carry a visible watermark, logo, or website name from ANOTHER property site or "
        "real-estate agency (e.g. text overlays like a company name, website URL, or logo stamped in a corner)? "
        "If a foreign watermark is present, this is very likely a photo scraped from another listing and must fail. "
        "Respond with JSON only, no markdown, no explanation outside the JSON: "
        "{\"status\": \"passed\" or \"failed\", \"feedback\": \"short reason, max 15 words, name the exact problem\"}"
    ),
    'id_document': (
        "You check identity document uploads for a Kenyan verification system. Look at this image and judge: "
        "1) Does it show an actual ID document (e.g. National ID card, passport) with visible text/photo, "
        "not a blank page, random object, or unrelated photo? "
        "2) Is it clear and legible enough to read (not blurry, not cropped/cut off, not too dark, not a "
        "screenshot of a screenshot)? "
        "Respond with JSON only, no markdown: "
        "{\"status\": \"passed\" or \"failed\", \"feedback\": \"short reason, max 15 words\"}"
    ),
    'business_document': (
        "You check business verification document uploads (registration certificate, KRA PIN certificate, "
        "business permit) for a Kenyan business directory. Look at this image and judge: "
        "1) Does it look like an official document/certificate with visible printed text, stamps, or letterhead "
        "(not a blank page, random photo, or unrelated image)? "
        "2) Is it clear and legible (not blurry, not cut off, not too dark)? "
        "Respond with JSON only, no markdown: "
        "{\"status\": \"passed\" or \"failed\", \"feedback\": \"short reason, max 15 words\"}"
    ),
}

@require_POST
def check_image_ai(request):
    """Pre-submit AJAX image check used by residence photos, ID upload, and business docs."""
    if not check_submission_rate_limit(request, 'ai_check_image', limit=30, window_seconds=3600):
        return JsonResponse({'ok': False, 'status': 'unchecked', 'feedback': 'Too many checks, slow down.'}, status=429)

    image = request.FILES.get('image')
    mode = request.POST.get('mode', 'property')
    if not image:
        return JsonResponse({'ok': False, 'status': 'unchecked', 'feedback': 'No image received.'}, status=400)
    if mode not in _IMAGE_CHECK_PROMPTS:
        mode = 'property'

    status, feedback = _groq_image_check(image, mode=mode)
    return JsonResponse({'ok': status != 'failed', 'status': status, 'feedback': feedback})


@require_POST
def check_location_ai(request):
    """
    Pre-submit location sanity check. Geocodes the claimed town/county and
    compares it against the pinned GPS coordinates (same Nominatim approach
    already used in verify_location for staff review). Hard-fails only on a
    large mismatch (wrong town/county entirely); a claimed landmark that OSM
    can't confirm is returned as a soft warning, since OSM coverage in Kenya
    is patchy and shouldn't block a genuine listing.
    """
    if not check_submission_rate_limit(request, 'ai_check_location', limit=20, window_seconds=3600):
        return JsonResponse({'ok': True, 'status': 'unchecked', 'feedback': 'Too many checks, slow down.'}, status=429)

    import requests
    from math import radians, sin, cos, sqrt, atan2
    from .amenity_check import check_nearby_amenities

    town = request.POST.get('town', '').strip()
    county = request.POST.get('county', '').strip()
    nearest_stage = request.POST.get('nearest_stage', '').strip()
    lat = request.POST.get('latitude')
    lng = request.POST.get('longitude')

    if not (town and county and lat and lng):
        return JsonResponse({'ok': True, 'status': 'unchecked', 'feedback': ''})

    try:
        lat, lng = float(lat), float(lng)
    except ValueError:
        return JsonResponse({'ok': True, 'status': 'unchecked', 'feedback': ''})

    def haversine_km(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 6371 * 2 * atan2(sqrt(a), sqrt(1 - a))

    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': f"{town}, {county}, Kenya", 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'HomeFinderKE/1.0 (homefinder.ke.help@gmail.com)'},
            timeout=8,
        )
        data = resp.json()
    except Exception as e:
        print("LOCATION CHECK GEOCODE ERROR:", e)
        return JsonResponse({'ok': True, 'status': 'unchecked', 'feedback': ''})

    if not data:
        # OSM has no record of that town/county spelling — can't verify, don't block
        return JsonResponse({'ok': True, 'status': 'unchecked', 'feedback': ''})

    expected_lat, expected_lng = float(data[0]['lat']), float(data[0]['lon'])
    distance_km = round(haversine_km(lat, lng, expected_lat, expected_lng), 1)

    if distance_km > 40:
        return JsonResponse({
            'ok': False,
            'status': 'failed',
            'feedback': f"Your pin is ~{distance_km}km from {town}, {county}. Please re-check the map pin or the town/county fields.",
        })

    # Soft check: does the claimed nearest stage actually exist near this pin?
    warning = ''
    if nearest_stage:
        amenity_result = check_nearby_amenities(lat, lng, claimed_stage=nearest_stage)
        if amenity_result.get('checked') and amenity_result.get('stage_match') is False:
            warning = f"Note: we couldn't confirm a stage called '{nearest_stage}' near this pin — double-check it's correct."

    return JsonResponse({'ok': True, 'status': 'passed' if not warning else 'warning', 'feedback': warning})

def _groq_image_check(image_field, mode='property'):
    """Vision check via Groq (free tier). Returns (status, feedback) where status is 'passed'/'failed'/'unchecked'."""
    try:
        client = _get_groq_client()
        image_bytes = image_field.read()
        image_field.seek(0)
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = _IMAGE_CHECK_PROMPTS.get(mode, _IMAGE_CHECK_PROMPTS['property'])

        response = client.chat.completions.create(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=80,
        )
        text = response.choices[0].message.content.strip().strip('`').replace('json', '').strip()
        data = json.loads(text)
        return data.get('status', 'unchecked'), data.get('feedback', '')
    except Exception as e:
        print("GROQ IMAGE CHECK ERROR:", e)
        return 'unchecked', ''

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

def get_started(request):
    return render(request, 'core/get_started.html')


def set_account_intent(request, account_type):
    if account_type not in ('resident', 'business'):
        return redirect('get_started')
    request.session['intended_account_type'] = account_type
    return redirect(f"{reverse('account_signup')}?type={account_type}")


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

@require_POST
def ai_fix_description(request):
    import json
    if request.user.is_authenticated and not check_submission_rate_limit(request, 'ai_fix_description', limit=10, window_seconds=3600):
        return JsonResponse({'error': 'Too many requests. Please slow down and try again shortly.'}, status=429)
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
            try:
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
                    fail_silently=False,
                )
                messages.success(request, 'Your message has been sent successfully.')
            except Exception as e:
                print("CONTACT FORM EMAIL ERROR:", e)
                messages.error(request, "Sorry, your message couldn't be sent right now. Please try again shortly, or reach us directly at homefinder.ke.help@gmail.com.")
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
    if business_account_blocked(request):
        return redirect('business:dashboard')
    residences = Residence.objects.filter(approved=True, is_hidden=False).order_by('-is_premium', '-created_at')
    paginator  = Paginator(residences, 9)
    page_obj   = paginator.get_page(request.GET.get('page'))
    return render(request, 'core/residence_list.html', {'page_obj': page_obj})


DIRECTORY_CATEGORY_ICONS = {
    'movers': '🚚', 'furniture': '🛋️', 'curtains': '🪟', 'electronics': '📺',
    'kitchen': '🍽️', 'mattresses': '🛏️', 'bathroom': '🛁', 'cleaning': '🧹',
    'lighting': '💡', 'repairs': '🛠️', 'garden': '🌿', 'internet': '🌐',
    'security': '🔒', 'househelp': '🧑‍🔧', 'carpets': '🧶', 'bedding': '🧺',
    'sofas': '🛋️', 'beds': '🛏️', 'wardrobes': '🚪', 'dining_furniture': '🍽️',
    'tv_stands': '📺', 'office_furniture': '🪑', 'interior_design': '🎨', 'home_decor': '🖼️',
    'blinds': '🪟', 'rugs': '🧶', 'wood_flooring': '🪵', 'tiles': '🔲', 'vinyl_flooring': '🧱',
    'tv_sound': '🔊', 'fridges': '🧊', 'washing_machines': '🧺', 'cookers': '🍳',
    'microwaves': '📻', 'water_dispensers': '🚰', 'air_conditioning': '❄️', 'fans': '🌀',
    'smart_devices': '🤖', 'kitchen_utensils': '🍴', 'cookware': '🍲', 'tableware': '🍽️',
    'kitchen_cabinets': '🗄️', 'kitchen_design': '👨‍🍳', 'shower_installation': '🚿',
    'water_heaters': '♨️', 'bathroom_fittings': '🛁', 'sanitaryware': '🚽', 'mirrors': '🪞',
    'electricians': '🔌', 'led_lighting': '💡', 'chandeliers': '🕯️', 'ceiling_lights': '💡',
    'outdoor_lighting': '🔦', 'smart_lighting': '💡', 'switches_sockets': '🔌',
    'solar_systems': '☀️', 'backup_power': '🔋', 'plumbers': '🔧', 'boreholes': '⛲',
    'water_delivery': '🚛', 'water_tanks': '🛢️', 'water_filters': '💧', 'pumps': '⚙️',
    'drainage': '🕳️', 'cctv_installers': '📹', 'alarm_systems': '🚨', 'electric_fencing': '⚡',
    'smart_locks': '🔐', 'door_access': '🚪', 'wifi_installation': '📶', 'starlink': '🛰️',
    'networking': '🌐', 'smart_automation': '🏠', 'packers': '📦', 'storage_companies': '🏬',
    'warehouses': '🏭', 'move_cleaning': '🧹', 'truck_hire': '🚛', 'painters': '🎨',
    'welders': '🔥', 'carpenters': '🪚', 'contractors': '👷', 'masonry': '🧱', 'roofing': '🏠',
    'ceiling_installers': '🏠', 'aluminium_windows': '🪟', 'glass_installers': '🪟',
    'gate_fabricators': '🚧', 'landscaping': '🌳', 'tree_cutting': '🪓', 'lawn_maintenance': '🌱',
    'pool_maintenance': '🏊', 'laundry': '🧺', 'pest_control': '🐛', 'garbage_collection': '🗑️',
    'nannies': '👶', 'caregivers': '🤝', 'babysitters': '🧸', 'private_chefs': '👨‍🍳',
    'laundry_pickup': '🧺', 'saccos': '🏦', 'mortgage_providers': '🏦', 'home_insurance': '🛡️',
    'banks': '🏦', 'valuers': '📋', 'pet_grooming': '🐕', 'vet_clinics': '🐾',
    'pet_stores': '🐈', 'dog_walkers': '🐕‍🦺', 'smart_cameras': '📷', 'smart_sensors': '📡',
    'smart_thermostats': '🌡️', 'home_automation': '🏠',
    'other': '📦',
}


class BusinessDirectoryAdapter:
    """
    Wraps a Business instance so it can render inside the same directory
    card loop as Mover/FurnitureVendor in moving_essentials.html without
    duplicating template markup — just proxies unmatched attributes
    straight through to the underlying Business.
    """
    def __init__(self, business):
        self._b = business
        self.distance_km = None

    def __getattr__(self, name):
        return getattr(self._b, name)

    @property
    def pk(self):
        return self._b.pk

    @property
    def image(self):
        return self._b.logo or self._b.cover_image

    @property
    def location(self):
        parts = [p for p in [self._b.estate, self._b.town, self._b.county] if p]
        return ', '.join(parts) if parts else (self._b.county or 'Kenya')

    @property
    def is_major_sponsor(self):
        return self._b.is_featured

    @property
    def detail_url(self):
        return reverse('business_detail', args=[self._b.slug])


def moving_essentials(request):
    from django.db.models import Q
    from business.models import BusinessProduct, CATEGORY_CHOICES as BUSINESS_CATEGORY_CHOICES

    county = request.GET.get('county', '').strip()
    category = request.GET.get('category', '').strip()
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')

    movers_qs = Mover.objects.filter(is_approved=True).prefetch_related(
        Prefetch('products', queryset=MoverProduct.objects.filter(is_active=True))
    )
    vendors_qs = FurnitureVendor.objects.filter(is_approved=True).prefetch_related(
        Prefetch('products', queryset=FurnitureProduct.objects.filter(is_active=True))
    )
    businesses_qs = Business.objects.filter(is_approved=True, is_active=True, is_paused_by_owner=False).select_related('owner').prefetch_related(
        Prefetch('products', queryset=BusinessProduct.objects.filter(is_available=True))
    )

    if county:
        movers_qs = movers_qs.filter(service_counties__icontains=county)
        vendors_qs = vendors_qs.filter(service_counties__icontains=county)
        businesses_qs = businesses_qs.filter(
            Q(service_counties__icontains=county) | Q(county__icontains=county)
        )

    if category and category != 'movers':
        vendors_qs = vendors_qs.filter(category=category)
        businesses_qs = businesses_qs.filter(category=category)
    elif category == 'movers':
        vendors_qs = vendors_qs.none()
        businesses_qs = businesses_qs.filter(category='movers')

    movers = list(movers_qs) if category in ('', 'movers') else []
    for m in movers:
        m.detail_url = reverse('mover_detail', args=[m.pk])

    vendors = list(vendors_qs) if category != 'movers' else []
    for v in vendors:
        v.detail_url = reverse('furniture_vendor_detail', args=[v.pk])

    for b in businesses_qs:
        adapter = BusinessDirectoryAdapter(b)
        if b.category == 'movers':
            movers.append(adapter)
        else:
            vendors.append(adapter)

    if user_lat and user_lng:
        for obj in movers + vendors:
            try:
                obj.distance_km = haversine_km(user_lat, user_lng, getattr(obj, 'latitude', None), getattr(obj, 'longitude', None))
            except (TypeError, ValueError):
                obj.distance_km = None
        movers.sort(key=lambda o: (o.distance_km is None, not o.is_major_sponsor, o.distance_km or 9999))
        vendors.sort(key=lambda o: (o.distance_km is None, not o.is_major_sponsor, o.distance_km or 9999))
    else:
        for obj in movers + vendors:
            obj.distance_km = None
        movers.sort(key=lambda o: (not o.is_major_sponsor, -o.created_at.timestamp()))
        vendors.sort(key=lambda o: (not o.is_major_sponsor, -o.created_at.timestamp()))

    vendor_category_counts = {
        c['category']: c['count'] for c in
        FurnitureVendor.objects.filter(is_approved=True).values('category').annotate(count=Count('id'))
    }
    business_category_counts = {
        c['category']: c['count'] for c in
        Business.objects.filter(is_approved=True, is_active=True).values('category').annotate(count=Count('id'))
    }
    mover_count = Mover.objects.filter(is_approved=True).count() + business_category_counts.get('movers', 0)

    categories = []
    for key, label in BUSINESS_CATEGORY_CHOICES:
        if key == 'movers':
            count = mover_count
        else:
            count = vendor_category_counts.get(key, 0) + business_category_counts.get(key, 0)
        categories.append({
            'key': key, 'label': label, 'count': count,
            'icon': DIRECTORY_CATEGORY_ICONS.get(key, '📦'),
        })
    # Movers first, then everything else in the order defined on the Business model
    categories.sort(key=lambda c: (c['key'] != 'movers',))

    return render(request, 'core/moving_essentials.html', {
        'movers': movers,
        'vendors': vendors,
        'selected_county': county,
        'selected_category': category,
        'categories': categories,
        'has_location': bool(user_lat and user_lng),
    })

def directory_search_suggestions(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    movers = Mover.objects.filter(is_approved=True, name__icontains=q)[:5]
    vendors = FurnitureVendor.objects.filter(is_approved=True, name__icontains=q)[:5]
    results = [{'type': 'mover', 'name': m.name, 'url': f'/mover/{m.pk}/'} for m in movers]
    results += [{'type': 'vendor', 'name': v.name, 'url': f'/furniture-vendor/{v.pk}/'} for v in vendors]
    return JsonResponse({'results': results})

def haversine_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    lat1, lng1, lat2, lng2 = map(float, (lat1, lng1, lat2, lng2))
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    # Floating-point rounding can push `a` a hair above 1 for near-identical
    # coordinates, which makes math.asin() raise "math domain error". Clamp it.
    return R * 2 * math.asin(min(1.0, math.sqrt(max(0.0, a))))

def residence_detail(request, pk):
    if business_account_blocked(request):
        return redirect('business:dashboard')
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

    # Only Premium (paying/sponsored) businesses are showcased on residence pages.
    # Free/unpaid directory listings no longer appear here — that's now exclusive
    # to the Home Directory page itself.
    sponsored_movers = list(
        Mover.objects.filter(is_approved=True, is_major_sponsor=True)
        .filter(service_counties__icontains=residence.county)
        .prefetch_related(
            Prefetch('products', queryset=MoverProduct.objects.filter(is_active=True))
        )
        .order_by('-created_at')[:6]
    )
    sponsored_vendors = list(
        FurnitureVendor.objects.filter(is_approved=True, is_major_sponsor=True)
        .filter(service_counties__icontains=residence.county)
        .prefetch_related(
            Prefetch('products', queryset=FurnitureProduct.objects.filter(is_active=True))
        )
        .order_by('-created_at')[:6]
    )
    movers = sponsored_movers
    vendors = sponsored_vendors

    share_url = request.build_absolute_uri()
    share_text = f"Check out {residence.name} on HomeFinder Kenya: {share_url}"

    context = {
        'residence': residence,
        'related_residences': related_residences,
        'movers': movers,
        'vendors': vendors,
        'sponsored_movers': sponsored_movers,
        'sponsored_vendors': sponsored_vendors,
        'share_url': share_url,
        'share_text': share_text,
    }
    return render(request, 'core/residence_detail.html', context)

def check_submission_rate_limit(request, action_name, limit=5, window_seconds=3600):
    from django.core.cache import cache
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
    key = f"rate_limit_{action_name}_{ip}"
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, timeout=window_seconds)
    return True

MAX_LISTINGS_PER_OWNER = 5

@login_required
def add_residence(request):
    if request.user.email == 'homefinder.ke.help@gmail.com':
        return redirect('admin_dashboard')
    if not check_not_suspended(request):
        return redirect('home')

    current_listing_count = Residence.objects.filter(owner=request.user).count()
    if current_listing_count >= MAX_LISTINGS_PER_OWNER:
        messages.error(request, f'You have reached the maximum of {MAX_LISTINGS_PER_OWNER} listings.Thanks for the contibibution add a friend to also add ')
        return redirect('dashboard')

    if request.method == 'POST':
        if not check_submission_rate_limit(request, 'add_residence', limit=10, window_seconds=3600):
            messages.error(request, 'Too many listings submitted recently. Please try again in an hour.')
            return redirect('add_residence')
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

                ListingAgreement.objects.create(
                    residence=residence,
                    owner=request.user,
                    terms_version=CURRENT_TERMS_VERSION,
                    terms_snapshot=LISTING_TERMS_TEXT,
                    ip_address=request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )

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


def listing_terms(request):
    return render(request, 'core/listing_terms.html', {
        'terms_text': LISTING_TERMS_TEXT,
        'version': CURRENT_TERMS_VERSION,
    })


# ── Replace your existing `dashboard` view in core/views.py with this one ──
# It keeps the same URL/name, just adds the context the new template needs.
# Everything here is built from models that already exist (Residence, Favorite,
# Review, Notification, Profile) — no new migrations required.

@login_required
def dashboard(request):
    if request.user.email == 'homefinder.ke.help@gmail.com':
        return redirect('admin_dashboard')

    from django.db.models import Avg, Count, Sum
    from datetime import timedelta

    residences = Residence.objects.filter(owner=request.user).order_by('-created_at')

    agg = residences.aggregate(
        total_views=Sum('views_count'),
        avg_rating=Avg('reviews__rating'),
    )
    total_listings = residences.count()
    active_listings = residences.filter(approved=True, is_hidden=False, is_paused=False).count()
    pending_listings = residences.filter(approved=False).count()
    total_views = agg['total_views'] or 0
    avg_rating = round(agg['avg_rating'], 1) if agg['avg_rating'] else None

    total_favorites = Favorite.objects.filter(residence__owner=request.user).count()
    total_reviews = Review.objects.filter(residence__owner=request.user).count()

    # ── Profile completion checklist ──
    profile = getattr(request.user, 'profile', None)
    checklist = [
        {'label': 'Profile photo', 'done': bool(profile and profile.profile_picture)},
        {'label': 'Phone number added', 'done': bool(profile and profile.phone_number)},
        {'label': 'Bio added', 'done': bool(profile and profile.bio)},
        {'label': 'Email on file', 'done': bool(request.user.email)},
        {'label': 'First listing added', 'done': total_listings > 0},
    ]
    done_count = sum(1 for c in checklist if c['done'])
    profile_completion = round((done_count / len(checklist)) * 100)

    # ── Recent activity (from Notification model) ──
    recent_activity = request.user.notifications.all().order_by('-created_at')[:6]

    # ── Simple views trend for the last 8 weeks (based on created_at cohorts) ──
    # Residence doesn't track per-day views historically, so this buckets each
    # listing's current views_count by the week it was created — a reasonable
    # proxy chart until real time-series view tracking exists.
    today = timezone.now().date()
    weeks = []
    for i in range(7, -1, -1):
        week_start = today - timedelta(days=today.weekday() + i * 7)
        week_end = week_start + timedelta(days=6)
        views_in_week = residences.filter(
            created_at__date__gte=week_start, created_at__date__lte=week_end
        ).aggregate(total=Sum('views_count'))['total'] or 0
        weeks.append({'label': week_start.strftime('%b %d'), 'views': views_in_week})

    context = {
        'residences': residences,
        'stats': {
            'total_listings': total_listings,
            'active_listings': active_listings,
            'pending_listings': pending_listings,
            'total_views': total_views,
            'total_favorites': total_favorites,
            'total_reviews': total_reviews,
            'avg_rating': avg_rating,
        },
        'checklist': checklist,
        'profile_completion': profile_completion,
        'recent_activity': recent_activity,
        'weekly_views': weeks,
    }
    return render(request, 'core/dashboard.html', context)


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

    # Businesses (from the business app's self-serve onboarding flow) that
    # finished onboarding and are waiting on admin approval before they can
    # appear on the public /moving-essentials/ directory.
    pending_businesses = Business.objects.filter(
        is_approved=False, onboarding_complete=True
    ).select_related('owner').order_by('-created_at')

    context = {
        'pending_businesses':   pending_businesses,
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
    if business_account_blocked(request):
        return redirect('business:dashboard')
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


def business_account_blocked(request):
    """Returns True (with an info message set) if a business account is trying to reach
    a residence-only feature (browsing residences, favorites, roommates, chat)."""
    if request.user.is_authenticated and getattr(request.user.profile, 'account_type', 'resident') == 'business':
        messages.info(request, 'This section is for residence accounts. Manage your business from your dashboard instead.')
        return True
    return False
def reject_residence(request, pk):
    residence = get_object_or_404(Residence, pk=pk)
    residence.delete()
    return redirect('admin_dashboard')


@staff_or_help_admin_required
def approve_business(request, pk):
    business = get_object_or_404(Business, pk=pk)
    business.is_approved = True
    business.is_active = True
    business.save(update_fields=['is_approved', 'is_active'])
    Notification.objects.create(
        user=business.owner,
        message=f'🎉 Your business "{business.name}" has been approved and is now live on the directory.'
    )
    messages.success(request, f'"{business.name}" approved and is now live.')
    return redirect('admin_dashboard')


@staff_or_help_admin_required
def reject_business(request, pk):
    business = get_object_or_404(Business, pk=pk)
    business.verification_status = 'rejected'
    business.is_approved = False
    business.is_active = False
    business.save(update_fields=['verification_status', 'is_approved', 'is_active'])
    Notification.objects.create(
        user=business.owner,
        message=f'Your business "{business.name}" listing was not approved. Please review your details and contact support if you have questions.'
    )
    messages.success(request, f'"{business.name}" rejected.')
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

    is_owner_viewing = request.user.is_authenticated and request.user.id == owner.id
    is_private = (
        profile.profile_visibility == 'private'
        and not is_owner_viewing
        and not request.user.is_staff
    )

    context = {
        'owner': owner,
        'profile': profile,
        'residences': residences,
        'is_private': is_private,
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
def settings_profile(request):
    """Settings > My Profile (Residence Workspace).
    Handles both the User fields (name/username/email) and the
    Profile fields (photos/phone/county/town/bio/language) in one save.
    """
    profile = request.user.profile

    if request.method == 'POST':
        user_form = SettingsUserForm(request.POST, instance=request.user)
        profile_form = SettingsProfileForm(request.POST, request.FILES, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('settings_profile')
    else:
        user_form = SettingsUserForm(instance=request.user)
        profile_form = SettingsProfileForm(instance=profile)

    return render(request, 'core/settings/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'active_section': 'profile',
    })


@login_required
def settings_security(request):
    """Settings > Security (Residence Workspace).
    Surfaces allauth's existing password-change + TOTP 2FA views,
    plus a read-only Login Activity / Trusted Devices list built on
    the existing accounts.KnownDevice model, plus a
    Logout Other Devices action (deletes all other DB sessions for
    this user, keeping the current one).
    """
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'logout_other_devices':
            current_key = request.session.session_key
            count = 0
            for s in Session.objects.filter(expire_date__gte=timezone.now()):
                data = s.get_decoded()
                if str(data.get('_auth_user_id')) == str(request.user.id) and s.session_key != current_key:
                    s.delete()
                    count += 1
            messages.success(request, f'Logged out of {count} other device(s).')

        elif action == 'remove_device':
            KnownDevice.objects.filter(user=request.user, id=request.POST.get('device_id')).delete()
            messages.success(request, 'Device removed.')

        return redirect('settings_security')

    devices = KnownDevice.objects.filter(user=request.user).order_by('-last_seen')
    mfa_enabled = Authenticator.objects.filter(user=request.user, type=Authenticator.Type.TOTP).exists()

    return render(request, 'core/settings/security.html', {
        'active_section': 'security',
        'devices': devices,
        'mfa_enabled': mfa_enabled,
    })


@login_required
def notifications(request):
    notifications = request.user.notifications.all().order_by('-created_at')
    notifications.update(is_read=True)
    return render(request, 'notifications.html', {'notifications': notifications})


@login_required
def settings_notifications(request):
    """Settings > Notifications (Residence Workspace)."""
    prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=prefs)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification preferences updated.')
            return redirect('settings_notifications')
    else:
        form = NotificationPreferenceForm(instance=prefs)

    return render(request, 'core/settings/notifications.html', {
        'form': form,
        'active_section': 'notifications',
    })


@login_required
def settings_appearance(request):
    """Settings > Appearance (Residence Workspace).
    Theme + Reduce Motion are applied site-wide via base.html reading
    request.user.profile.theme_preference / reduce_motion.
    Compact Mode is stored here but, for now, only affects the
    Settings pages themselves — not yet wired site-wide.
    """
    profile = request.user.profile

    if request.method == 'POST':
        form = AppearanceForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Appearance preferences updated.')
            return redirect('settings_appearance')
    else:
        form = AppearanceForm(instance=profile)

    return render(request, 'core/settings/appearance.html', {
        'form': form,
        'active_section': 'appearance',
    })


@login_required
def settings_privacy(request):
    """Settings > Privacy (Residence Workspace).
    Profile Visibility and Hide Phone are actually enforced in
    owner_profile(). Hide Email is stored but not yet enforced
    anywhere, since email isn't shown publicly on the site today.
    """
    profile = request.user.profile

    if request.method == 'POST':
        form = PrivacyForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Privacy settings updated.')
            return redirect('settings_privacy')
    else:
        form = PrivacyForm(instance=profile)

    return render(request, 'core/settings/privacy.html', {
        'form': form,
        'active_section': 'privacy',
    })


@login_required
def settings_saved(request):
    """Settings > Saved Items (Residence Workspace).
    Aggregates existing Favorite / MoverFavorite / FurnitureVendorFavorite /
    SavedSearch / ResidenceView models — no new tables needed.
    Removing a mover/vendor favorite is handled here (no existing endpoint
    for that); removing a residence favorite or saved search links out to
    the existing remove_favorite / delete_saved_search views.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'remove_mover_favorite':
            MoverFavorite.objects.filter(user=request.user, id=request.POST.get('id')).delete()
            messages.success(request, 'Removed from saved movers.')
        elif action == 'remove_vendor_favorite':
            FurnitureVendorFavorite.objects.filter(user=request.user, id=request.POST.get('id')).delete()
            messages.success(request, 'Removed from saved furniture vendors.')
        return redirect('settings_saved')

    return render(request, 'core/settings/saved.html', {
        'active_section': 'saved',
        'favorites': Favorite.objects.filter(user=request.user).select_related('residence').order_by('-created_at'),
        'mover_favorites': MoverFavorite.objects.filter(user=request.user).select_related('mover').order_by('-created_at'),
        'vendor_favorites': FurnitureVendorFavorite.objects.filter(user=request.user).select_related('vendor').order_by('-created_at'),
        'saved_searches': SavedSearch.objects.filter(user=request.user).order_by('-created_at'),
        'recently_viewed': ResidenceView.objects.filter(user=request.user).select_related('residence').order_by('-last_viewed')[:10],
    })


@login_required
def settings_help(request):
    """Settings > Help & Support (Residence Workspace).
    Links out to existing pages (about/terms_of_service/privacy_policy).
    No FAQ/Help Center page exists yet, and "Rate Application" doesn't
    apply to a web app, so both are left out rather than faked.
    """
    return render(request, 'core/settings/help.html', {
        'active_section': 'help',
    })


from django.contrib.auth import logout
from allauth.account.models import EmailAddress


@login_required
def settings_verification(request):
    """Settings > Verification (Residence Workspace).
    National ID upload/status is real (IDVerification model, reviewed
    manually via Django admin for now — a dedicated staff review page
    is a natural follow-up). Email status reads allauth's existing
    EmailAddress.verified rather than duplicating that state. Phone
    verification has no OTP system behind it yet, so it always shows
    "Not Available" rather than faking a working flow.
    """
    verification, _ = IDVerification.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = IDVerificationForm(request.POST, request.FILES, instance=verification)
        if form.is_valid():
            verification = form.save(commit=False)
            verification.status = 'pending'
            verification.submitted_at = timezone.now()
            verification.save()
            messages.success(request, 'Document submitted for review.')
            return redirect('settings_verification')
    else:
        form = IDVerificationForm(instance=verification)

    email_address = EmailAddress.objects.filter(user=request.user, primary=True).first()
    email_verified = email_address.verified if email_address else False

    checks_passed = sum([
        email_verified,
        request.user.profile.phone_verified,
        verification.status == 'verified',
    ])

    return render(request, 'core/settings/verification.html', {
        'active_section': 'verification',
        'form': form,
        'verification': verification,
        'email_verified': email_verified,
        'progress_percent': int((checks_passed / 3) * 100),
    })


@login_required
def settings_danger(request):
    """Settings > Danger Zone (Residence Workspace).
    Deactivate uses Django's built-in User.is_active (blocks login
    immediately). Deliberately kept separate from the staff-only
    Profile.is_suspended flag used for policy enforcement, so a
    self-deactivation can never be confused with a staff suspension.
    Reactivation currently requires contacting support — a self-service
    reactivation link is a separate feature, not built here.
    Delete Account is a real hard delete (Residence.owner already uses
    on_delete=CASCADE, matching the hard-delete convention already used
    for vendor removal elsewhere) and requires the account password to
    confirm before anything happens.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        password = request.POST.get('password', '')

        if not request.user.check_password(password):
            messages.error(request, 'Incorrect password. No changes were made.')
            return redirect('settings_danger')

        if action == 'deactivate':
            request.user.is_active = False
            request.user.save()
            logout(request)
            messages.success(request, 'Your account has been deactivated. Contact homefinder.ke.help@gmail.com to reactivate it.')
            return redirect('home')

        elif action == 'delete_account':
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, 'Your account and all associated data have been permanently deleted.')
            return redirect('home')

    return render(request, 'core/settings/danger.html', {
        'active_section': 'danger',
    })


@login_required
def settings_export_data(request):
    """Settings > Danger Zone > Export Data.
    Downloads the user's own Profile fields, favorites, saved searches,
    and owned residence listings as a JSON file.
    """
    profile = request.user.profile
    data = {
        'account': {
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'date_joined': request.user.date_joined.isoformat(),
        },
        'profile': {
            'phone_number': profile.phone_number,
            'bio': profile.bio,
            'county': profile.county,
            'town': profile.town,
        },
        'favorited_residences': list(
            Favorite.objects.filter(user=request.user).values_list('residence__name', flat=True)
        ),
        'saved_searches': list(
            SavedSearch.objects.filter(user=request.user).values(
                'keyword', 'county', 'town', 'house_type', 'min_rent', 'max_rent'
            )
        ),
        'owned_residences': list(
            Residence.objects.filter(owner=request.user).values('name', 'town', 'county', 'rent_price')
        ),
    }
    response = HttpResponse(json.dumps(data, indent=2, default=str), content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="homefinderke_my_data.json"'
    return response


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
    if business_account_blocked(request):
        return redirect('business:dashboard')
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
    expired_movers = Mover.objects.filter(contract_expires_at__lt=today)
    expired_vendors = FurnitureVendor.objects.filter(contract_expires_at__lt=today)
    count = expired_movers.count() + expired_vendors.count()
    expired_movers.delete()
    expired_vendors.delete()
    messages.success(request, f'Removed {count} expired contract(s).')
    return redirect('vendor_dashboard')

@login_required
def save_mover_favorite(request, pk):
    mover = get_object_or_404(Mover, pk=pk, is_approved=True)
    favorite, created = MoverFavorite.objects.get_or_create(user=request.user, mover=mover)
    if created:
        messages.success(request, 'Mover saved to your favorites.')
    else:
        messages.info(request, 'Already in your favorites.')
    return redirect('mover_detail', pk=mover.pk)


@login_required
def save_furniture_vendor_favorite(request, pk):
    vendor = get_object_or_404(FurnitureVendor, pk=pk, is_approved=True)
    favorite, created = FurnitureVendorFavorite.objects.get_or_create(user=request.user, vendor=vendor)
    if created:
        messages.success(request, 'Vendor saved to your favorites.')
    else:
        messages.info(request, 'Already in your favorites.')
    return redirect('furniture_vendor_detail', pk=vendor.pk)

def mover_detail(request, pk):
    mover = get_object_or_404(Mover, pk=pk, is_approved=True)
    if request.method == 'POST' and request.user.is_authenticated:
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        if rating:
            MoverReview.objects.update_or_create(
                mover=mover, user=request.user,
                defaults={'rating': int(rating), 'comment': comment}
            )
            messages.success(request, "Thanks for your review!")
            return redirect('mover_detail', pk=mover.pk)
    reviews = mover.reviews.select_related('user')[:20]
    return render(request, 'core/mover_detail.html', {'mover': mover, 'reviews': reviews})

def furniture_vendor_detail(request, pk):
    vendor = get_object_or_404(FurnitureVendor, pk=pk, is_approved=True)
    if request.method == 'POST' and request.user.is_authenticated:
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        if rating:
            FurnitureVendorReview.objects.update_or_create(
                vendor=vendor, user=request.user,
                defaults={'rating': int(rating), 'comment': comment}
            )
            messages.success(request, "Thanks for your review!")
            return redirect('furniture_vendor_detail', pk=vendor.pk)
    reviews = vendor.reviews.select_related('user')[:20]
    return render(request, 'core/furniture_vendor_detail.html', {'vendor': vendor, 'reviews': reviews})


def business_detail(request, slug):
    from business.models import (
        BusinessAnalyticsEvent, BusinessBooking, BusinessFavorite, BusinessInquiry,
        BusinessOrder, BusinessOrderItem, BusinessReview,
    )
    business = get_object_or_404(Business, slug=slug, is_approved=True, is_active=True, is_paused_by_owner=False)

    if request.method == 'POST':
        if request.POST.get('form_type') == 'inquiry':
            message = request.POST.get('message', '').strip()
            name = request.POST.get('customer_name', '').strip()
            if message and name:
                BusinessInquiry.objects.create(
                    business=business,
                    customer=request.user if request.user.is_authenticated else None,
                    customer_name=name,
                    customer_phone=request.POST.get('customer_phone', '').strip(),
                    customer_email=request.POST.get('customer_email', '').strip(),
                    message=message,
                )
                messages.success(request, "Message sent! The business will get back to you directly.")
            return redirect('business_detail', slug=business.slug)
        elif request.POST.get('form_type') == 'order' and request.user.is_authenticated:
            if not business.has_feature('order_management'):
                messages.error(request, "This business isn't set up to take online orders yet — try WhatsApp or phone instead.")
                return redirect('business_detail', slug=business.slug)

            product = business.products.filter(pk=request.POST.get('product_id'), is_available=True).first()
            name = request.POST.get('customer_name', '').strip()
            quantity = request.POST.get('quantity', '1')
            try:
                quantity = max(1, int(quantity))
            except (TypeError, ValueError):
                quantity = 1

            if not product or not name:
                messages.error(request, "Choose a product and enter your name to place an order.")
            else:
                order = BusinessOrder.objects.create(
                    business=business, customer=request.user, customer_name=name,
                    customer_phone=request.POST.get('customer_phone', '').strip(),
                    delivery_address=request.POST.get('delivery_address', '').strip(),
                )
                BusinessOrderItem.objects.create(
                    order=order, product=product, product_name=product.name,
                    quantity=quantity, unit_price=product.price or 0,
                )
                order.total_amount = quantity * (product.price or 0)
                order.save(update_fields=['total_amount'])
                Notification.objects.create(
                    user=business.owner,
                    message=f'📦 New order from {name}: {quantity}× {product.name} — check your Orders dashboard to respond.'
                )
                messages.success(request, "Order request sent! The business will contact you directly to confirm and arrange payment.")
            return redirect('business_detail', slug=business.slug)
        elif request.POST.get('form_type') == 'booking' and request.user.is_authenticated:
            if not business.has_feature('bookings'):
                messages.error(request, "This business isn't set up to take online bookings yet — try WhatsApp or phone instead.")
                return redirect('business_detail', slug=business.slug)

            service = business.services.filter(pk=request.POST.get('service_id'), is_available=True).first()
            name = request.POST.get('customer_name', '').strip()
            requested_date = request.POST.get('requested_date', '')

            if not service or not name or not requested_date:
                messages.error(request, "Choose a service, a date, and enter your name to request a booking.")
            else:
                BusinessBooking.objects.create(
                    business=business, service=service, customer=request.user, customer_name=name,
                    customer_phone=request.POST.get('customer_phone', '').strip(),
                    customer_email=request.POST.get('customer_email', '').strip(),
                    requested_date=requested_date,
                    requested_time=request.POST.get('requested_time') or None,
                    notes=request.POST.get('notes', '').strip(),
                )
                Notification.objects.create(
                    user=business.owner,
                    message=f'📅 New booking request from {name} for {service.name} — check your Bookings dashboard to confirm.'
                )
                messages.success(request, "Booking request sent! The business will confirm with you directly.")
            return redirect('business_detail', slug=business.slug)
        elif request.POST.get('form_type') == 'favorite' and request.user.is_authenticated:
            fav, created = BusinessFavorite.objects.get_or_create(user=request.user, business=business)
            if not created:
                fav.delete()
            return redirect('business_detail', slug=business.slug)
        elif request.user.is_authenticated:
            rating = request.POST.get('rating')
            comment = request.POST.get('comment', '').strip()
            if rating:
                BusinessReview.objects.update_or_create(
                    business=business, user=request.user,
                    defaults={'rating': int(rating), 'comment': comment}
                )
                messages.success(request, "Thanks for your review!")
            return redirect('business_detail', slug=business.slug)

    BusinessAnalyticsEvent.objects.create(
        business=business, event_type='profile_view',
        user=request.user if request.user.is_authenticated else None,
    )
    reviews = business.reviews.select_related('user')[:20]
    total_reviews = business.review_count
    rating_breakdown = []
    for star in (5, 4, 3, 2, 1):
        count = business.reviews.filter(rating=star).count()
        pct = round((count / total_reviews) * 100) if total_reviews else 0
        rating_breakdown.append({'star': star, 'count': count, 'pct': pct})
    is_favorited = (
        request.user.is_authenticated
        and BusinessFavorite.objects.filter(user=request.user, business=business).exists()
    )
    related = Business.objects.filter(
        category=business.category, is_approved=True, is_active=True, is_paused_by_owner=False
    ).exclude(pk=business.pk)[:4]
    return render(request, 'core/business_detail.html', {
        'business': business, 'reviews': reviews, 'rating_breakdown': rating_breakdown,
        'is_favorited': is_favorited, 'related': related,
        'can_order': business.has_feature('order_management'),
        'can_book': business.has_feature('bookings'),
    })


def business_track_click(request, slug, event_type):
    from business.models import BusinessAnalyticsEvent
    if event_type in ('phone_click', 'whatsapp_click', 'website_click'):
        business = Business.objects.filter(slug=slug, is_approved=True).first()
        if business:
            BusinessAnalyticsEvent.objects.create(
                business=business, event_type=event_type,
                user=request.user if request.user.is_authenticated else None,
            )
    return HttpResponse(status=204)

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

def sentry_test(request):
    1 / 0
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
def download_agreement_pdf(request, pk):
    residence = get_object_or_404(Residence, pk=pk)
    agreement = get_object_or_404(ListingAgreement, residence=residence)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('AgreementTitle', parent=styles['Heading1'], textColor=colors.HexColor('#0F766E'))
    elements = []

    elements.append(Paragraph("HomeFinder KE — Listing Agreement Record", title_style))
    elements.append(Spacer(1, 14))

    data = [
        ['Residence', residence.name],
        ['Owner (username)', agreement.owner.username],
        ['Owner email', agreement.owner.email or '—'],
        ['Terms version', agreement.terms_version],
        ['Agreed at (server timestamp)', agreement.agreed_at.strftime('%d %B %Y, %H:%M:%S UTC')],
        ['IP address at consent', agreement.ip_address or 'Not captured'],
        ['User agent at consent', agreement.user_agent or 'Not captured'],
    ]
    table = Table(data, colWidths=[5.5*cm, 10.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0FDFA')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#99F6E4')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Terms Agreed To (Full Text, As Presented At Time Of Consent)", styles['Heading3']))
    elements.append(Spacer(1, 8))
    for line in agreement.terms_snapshot.strip().split('\n'):
        elements.append(Paragraph(line if line.strip() else '&nbsp;', styles['Normal']))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(
        "This document was generated automatically by HomeFinder KE and records the electronic "
        "consent given by the above user at the time of listing submission. It is not a substitute "
        "for independent legal advice.",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    ))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="agreement_{residence.id}_{residence.name.replace(" ", "_")}.pdf"'
    return response