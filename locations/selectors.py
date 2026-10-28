from datetime import timedelta

from django.db.models import (
    Avg,
    Count,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.functions import Cast, Coalesce, Ln
from django.utils import timezone

from .models import Location, LocationView, Review, ReviewVote

POPULARITY_VIEWS_WINDOW = timedelta(days=7)
POPULARITY_VIEWS_WEIGHT = 0.5


def _count_subquery(qs: QuerySet) -> Subquery:
    return Subquery(
        qs.order_by().values("location").annotate(c=Count("pk")).values("c"),
        output_field=IntegerField(),
    )


def annotate_location_stats(qs: QuerySet[Location]) -> QuerySet[Location]:
    reviews = Review.objects.filter(location=OuterRef("pk"))
    since = timezone.now() - POPULARITY_VIEWS_WINDOW
    views = LocationView.objects.filter(location=OuterRef("pk"), created_at__gte=since)

    avg_rating = Subquery(
        reviews.order_by().values("location").annotate(a=Avg("rating")).values("a"),
        output_field=FloatField(),
    )

    # Separate subqueries: joining reviews and views at once would multiply rows.
    qs = qs.annotate(
        rating=avg_rating,
        reviews_count=Coalesce(_count_subquery(reviews), 0),
        views_7d=Coalesce(_count_subquery(views), 0),
    )
    return qs.annotate(
        popularity=(
            Coalesce(F("rating"), Value(0.0)) * Ln(Cast(F("reviews_count"), FloatField()) + 1.0)
            + Value(POPULARITY_VIEWS_WEIGHT) * Ln(Cast(F("views_7d"), FloatField()) + 1.0)
        )
    )


def location_list_queryset() -> QuerySet[Location]:
    return annotate_location_stats(Location.objects.select_related("category", "author"))


def review_queryset(user) -> QuerySet[Review]:
    qs = (
        Review.objects.filter(location__is_deleted=False)
        .select_related("author")
        .annotate(
            likes=Count("votes", filter=Q(votes__value=ReviewVote.Value.LIKE)),
            dislikes=Count("votes", filter=Q(votes__value=ReviewVote.Value.DISLIKE)),
        )
    )
    if user.is_authenticated:
        my_vote = ReviewVote.objects.filter(review=OuterRef("pk"), user=user).values("value")[:1]
        return qs.annotate(my_vote=Subquery(my_vote, output_field=IntegerField()))
    return qs.annotate(my_vote=Value(None, output_field=IntegerField()))
