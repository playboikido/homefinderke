from rest_framework import serializers
from .models import Residence, ResidencePhoto, Review, Favorite


class ResidencePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResidencePhoto
        fields = ['id', 'image']


class ResidenceListSerializer(serializers.ModelSerializer):
    """Lightweight — used for the scrolling feed/search results."""
    front_image = serializers.ImageField(use_url=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Residence
        fields = [
            'id', 'name', 'house_type', 'rent_price', 'county', 'town',
            'landmark', 'front_image', 'is_premium', 'average_rating',
            'review_count', 'created_at',
        ]

    def get_average_rating(self, obj):
        return obj.average_rating()

    def get_review_count(self, obj):
        return obj.reviews.count()


class ResidenceDetailSerializer(serializers.ModelSerializer):
    """Full detail — used for the single-listing screen."""
    photos = ResidencePhotoSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = Residence
        fields = [
            'id', 'name', 'description', 'house_type', 'rent_price',
            'deposit_amount', 'county', 'town', 'plot_number', 'landmark',
            'nearest_stage', 'nearby_school', 'nearby_hospital',
            'phone_number', 'whatsapp_number', 'latitude', 'longitude',
            'water_available', 'fibre_available', 'gated_community',
            'cctv_available', 'security_guard', 'front_image',
            'vacancy_poster', 'photos', 'views_count', 'is_premium',
            'average_rating', 'review_count', 'is_favorited', 'created_at',
        ]

    def get_average_rating(self, obj):
        return obj.average_rating()

    def get_review_count(self, obj):
        return obj.reviews.count()

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return Favorite.objects.filter(user=request.user, residence=obj).exists()