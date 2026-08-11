from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Residence, Favorite
from .serializers import ResidenceListSerializer, ResidenceDetailSerializer


class ResidenceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/residences/            -> list (search + filter)
    /api/residences/{id}/       -> detail
    /api/residences/{id}/favorite/  -> POST to toggle favorite
    """
    queryset = Residence.objects.filter(approved=True, is_hidden=False).order_by(
        '-is_premium', '-views_count', '-created_at'
    )
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['county', 'town', 'house_type']
    search_fields = ['name', 'landmark', 'nearest_stage', 'county', 'town']
    ordering_fields = ['rent_price', 'created_at', 'views_count']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ResidenceDetailSerializer
        return ResidenceListSerializer

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def favorite(self, request, pk=None):
        residence = self.get_object()
        favorite, created = Favorite.objects.get_or_create(user=request.user, residence=residence)
        if not created:
            favorite.delete()
            return Response({'favorited': False}, status=status.HTTP_200_OK)
        return Response({'favorited': True}, status=status.HTTP_201_CREATED)