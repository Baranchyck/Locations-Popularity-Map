from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from common.filters import NullsLastOrderingFilter
from common.permissions import IsAdminOrReadOnly, IsAuthorOrAdminOrReadOnly

from .filters import LocationFilter
from .models import Category
from .selectors import location_list_queryset
from .serializers import CategorySerializer, LocationSerializer
from .services import register_view


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [SearchFilter, NullsLastOrderingFilter]
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")
    ordering = ("name",)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            # on_delete=PROTECT on Location.category -> 409 instead of a 500.
            raise Conflict("Category is used by locations and can't be deleted.")


class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthorOrAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, NullsLastOrderingFilter]
    filterset_class = LocationFilter
    search_fields = ("name", "description")
    ordering_fields = ("created_at", "rating", "popularity")
    ordering = ("-created_at",)

    def get_queryset(self):
        # Default manager -> soft-deleted locations are excluded (404 on detail).
        return location_list_queryset()

    def perform_create(self, serializer):
        instance = serializer.save(author=self.request.user)
        # A freshly saved instance has no annotations (rating, popularity...):
        # re-read it through the annotated queryset before serializing.
        serializer.instance = self.get_queryset().get(pk=instance.pk)

    def perform_update(self, serializer):
        instance = serializer.save()
        serializer.instance = self.get_queryset().get(pk=instance.pk)

    # perform_destroy is inherited: instance.delete() is a soft delete.

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if register_view(request, instance):
            # Re-read so views_7d and popularity include the view just counted.
            instance = self.get_queryset().get(pk=instance.pk)
        return Response(self.get_serializer(instance).data)
