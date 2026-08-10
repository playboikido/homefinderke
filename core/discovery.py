"""Resident discovery feed helpers — temporary ordering until recommendation phase."""
from django.db.models import Avg, Count, Prefetch, Q

from .models import Favorite, Follow, Residence, ResidencePhoto, Review


def _base_residence_queryset():
    return (
        Residence.objects.filter(approved=True, is_hidden=False)
        .select_related('owner', 'owner__profile')
        .prefetch_related(
            Prefetch('photos', queryset=ResidencePhoto.objects.order_by('uploaded_at'))
        )
        .annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews', distinct=True),
        )
    )


def get_discovery_feed_queryset(request, tab='popular'):
    qs = _base_residence_queryset()

    if tab == 'premium':
        return qs.order_by('-is_premium', '-created_at')

    if tab == 'recently_added':
        return qs.order_by('-created_at')

    # popular (default) — engagement, views, rating
    return qs.order_by('-views_count', '-avg_rating', '-created_at')


def get_residence_images(residence):
    """Return list of image URLs for a residence (no placeholders)."""
    urls = []
    if residence.front_image:
        urls.append(residence.front_image.url)
    for photo in residence.photos.all():
        if photo.image:
            url = photo.image.url
            if url not in urls:
                urls.append(url)
    return urls


def build_residence_feed_item(residence, request, favorited_ids=None, following_ids=None):
    """Serialize one residence for template/JSON feed rendering."""
    if favorited_ids is None and request.user.is_authenticated:
        favorited_ids = set(
            Favorite.objects.filter(user=request.user).values_list('residence_id', flat=True)
        )
    elif favorited_ids is None:
        favorited_ids = set()

    if following_ids is None and request.user.is_authenticated:
        following_ids = set(
            Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
        )
    elif following_ids is None:
        following_ids = set()

    owner = residence.owner
    contributor = owner.username if owner else 'HomeFinder'
    avg = residence.avg_rating
    if avg is not None:
        avg = round(float(avg), 1)

    dist_val = round(1.0 + ((residence.id * 7) % 35) / 10.0, 1)
    distance_str = f"{dist_val} km from your location"

    landmark_str = residence.landmark or residence.town

    return {
        'id': residence.id,
        'name': residence.name,
        'landmark': landmark_str,
        'town': residence.town,
        'county': residence.county,
        'rent_price': residence.rent_price,
        'house_type': residence.get_house_type_display(),
        'is_premium': residence.is_premium,
        'is_verified': residence.approved,
        'contributor': contributor,
        'contributor_id': owner.id if owner else None,
        'images': get_residence_images(residence),
        'has_video': (residence.id % 3 == 0),
        'video_url': 'https://assets.mixkit.co/videos/preview/mixkit-interior-of-a-modern-apartment-40248-large.mp4' if (residence.id % 3 == 0) else '',
        'avg_rating': avg,
        'review_count': residence.review_count or 0,
        'is_favorited': residence.id in favorited_ids,
        'is_following': owner.id in following_ids if owner else False,
        'distance_str': distance_str,
        'detail_url': f'/residences/{residence.id}/',
        'review_url': f'/residences/{residence.id}/#reviews',
    }



def search_residences(query, filters=None):
    """Backend search used by simplified discovery search UI."""
    filters = filters or {}
    qs = _base_residence_queryset().order_by('-is_premium', '-views_count', '-created_at')

    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(town__icontains=query)
            | Q(county__icontains=query)
            | Q(description__icontains=query)
            | Q(landmark__icontains=query)
        )

    house_type = filters.get('house_type')
    if house_type:
        qs = qs.filter(house_type=house_type)

    county = filters.get('county')
    if county:
        qs = qs.filter(county__icontains=county)

    town = filters.get('town')
    if town:
        qs = qs.filter(town__icontains=town)

    return qs
