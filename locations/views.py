import logging

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from common.filters import NullsLastOrderingFilter
from common.permissions import IsAdminOrReadOnly, IsAuthorOrAdminOrReadOnly

from .cache import LIST_CACHE_TTL, list_cache_key
from .export import EXPORT_FORMATS, export_response
from .filters import LocationFilter
from .models import Category, LocationSubscription, Review, ReviewVote
from .selectors import location_list_queryset, review_queryset
from .serializers import CategorySerializer, LocationSerializer, ReviewSerializer, VoteSerializer
from .services import register_view
from .tasks import notify_new_review

logger = logging.getLogger(__name__)


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

    def list(self, request, *args, **kwargs):
        # The list doesn't depend on the current user, so one cache entry per
        # (host, path, query) is correct. If per-user fields are ever added,
        # the user must become part of the key.
        try:
            key = list_cache_key(request)
            cached = cache.get(key)
        except Exception:  # Redis down -> serve from DB
            logger.exception("Location list cache unavailable")
            key, cached = None, None

        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        if key is not None:
            try:
                cache.set(key, response.data, LIST_CACHE_TTL)
            except Exception:
                logger.exception("Failed to store location list in cache")
        return response

    @action(
        detail=True,
        methods=["get", "post"],
        serializer_class=ReviewSerializer,
        permission_classes=[IsAuthenticatedOrReadOnly],
        filter_backends=[],
    )
    def reviews(self, request, pk=None):
        """GET: reviews of the location. POST: leave a review (one per user)."""
        location = self.get_object()

        if request.method == "GET":
            # Explicit order: Meta.ordering is ignored in GROUP BY queries,
            # and pagination needs a deterministic order.
            qs = review_queryset(request.user).filter(location=location).order_by("-created_at", "-pk")
            page = self.paginate_queryset(qs)
            return self.get_paginated_response(self.get_serializer(page, many=True).data)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if Review.objects.filter(location=location, author=request.user).exists():
            raise Conflict("You have already reviewed this location.")
        try:
            with transaction.atomic():
                review = serializer.save(location=location, author=request.user)
                # Queue emails only after COMMIT: otherwise the worker may run
                # before the row is visible, or for a review that was rolled back.
                transaction.on_commit(lambda: notify_new_review.delay(review.pk))
        except IntegrityError:
            # Two parallel POSTs passed the exists() check; the DB constraint
            # review_one_per_user_location rejected the second one.
            raise Conflict("You have already reviewed this location.")

        review = review_queryset(request.user).get(pk=review.pk)
        return Response(self.get_serializer(review).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def export(self, request):
        """
        GET /locations/export/?file_format=csv|json  (+ any list filters/search/ordering).
        The param isn't called `format`: DRF reserves `?format=` for renderer selection.
        """
        file_format = request.query_params.get("file_format", "csv").lower()
        if file_format not in EXPORT_FORMATS:
            raise ValidationError({"file_format": f"Must be one of: {', '.join(EXPORT_FORMATS)}."})
        return export_response(self.filter_queryset(self.get_queryset()), file_format)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
        filter_backends=[],
    )
    def subscribe(self, request, pk=None):
        """Bonus. POST: get emails about new reviews of this location. DELETE: unsubscribe."""
        location = self.get_object()

        if request.method == "DELETE":
            deleted, _ = LocationSubscription.objects.filter(
                location=location, user=request.user
            ).delete()
            if not deleted:
                raise NotFound("You are not subscribed to this location.")
            return Response(status=status.HTTP_204_NO_CONTENT)

        # get_or_create is race-safe thanks to the unique constraint.
        _, created = LocationSubscription.objects.get_or_create(location=location, user=request.user)
        return Response(
            {"subscribed": True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if register_view(request, instance):
            # Re-read so views_7d and popularity include the view just counted.
            instance = self.get_queryset().get(pk=instance.pk)
        return Response(self.get_serializer(instance).data)


class ReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Reviews are created via POST /locations/{id}/reviews/.
    Here: list (filterable), retrieve, edit/delete (author or admin), voting.
    """

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthorOrAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, NullsLastOrderingFilter]
    filterset_fields = ("location", "author", "rating")
    ordering_fields = ("created_at", "rating")
    ordering = ("-created_at",)

    def get_queryset(self):
        return review_queryset(self.request.user)

    def perform_update(self, serializer):
        review = serializer.save()
        serializer.instance = self.get_queryset().get(pk=review.pk)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated],
        serializer_class=VoteSerializer,
    )
    def vote(self, request, pk=None):
        """
        POST {"value": 1 | -1}: like / dislike. One vote per user per review;
        posting again switches the vote. DELETE: withdraw the vote.
        """
        review = self.get_object()

        if request.method == "DELETE":
            deleted, _ = ReviewVote.objects.filter(review=review, user=request.user).delete()
            if not deleted:
                raise NotFound("You have not voted for this review.")
            return Response(status=status.HTTP_204_NO_CONTENT)

        if review.author_id == request.user.id:
            raise ValidationError("You can't vote for your own review.")
        serializer = VoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # update_or_create locks the row (SELECT ... FOR UPDATE) and, on a race
        # for the first vote, falls back to get() after the unique violation.
        _, created = ReviewVote.objects.update_or_create(
            review=review,
            user=request.user,
            defaults={"value": serializer.validated_data["value"]},
        )
        review = self.get_queryset().get(pk=review.pk)
        return Response(
            ReviewSerializer(review, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
