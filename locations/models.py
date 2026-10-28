from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from common.models import SoftDeleteModel, TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="category_name_ci_unique"),
        ]

    def __str__(self):
        return self.name


class Location(SoftDeleteModel, TimeStampedModel):
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # a category in use can't be removed
        related_name="locations",
    )
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,  # ~0.11 m precision
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # keep the location if the author account is removed
        null=True,
        related_name="locations",
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name="location_latitude_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name="location_longitude_range",
            ),
        ]

    def __str__(self):
        return self.name


class Review(TimeStampedModel):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    text = models.TextField()

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("location", "author"), name="review_one_per_user_location"
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5), name="review_rating_1_5"
            ),
        ]

    def __str__(self):
        return f"{self.author} -> {self.location} ({self.rating})"


class ReviewVote(models.Model):
    class Value(models.IntegerChoices):
        LIKE = 1, "like"
        DISLIKE = -1, "dislike"

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_votes"
    )
    value = models.SmallIntegerField(choices=Value.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("review", "user"), name="vote_one_per_user_review"),
            models.CheckConstraint(condition=Q(value__in=(1, -1)), name="vote_value_valid"),
        ]

    def __str__(self):
        return f"{self.user} {self.get_value_display()} review#{self.review_id}"


class LocationView(models.Model):
    """
    One row per counted view. Needed because popularity uses views for the
    last 7 days - a single counter column can't answer "how many in a window".
    De-duplication (1 per viewer per hour) happens in Redis before insert.
    """

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="location_views",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # Serves: WHERE location_id = ? AND created_at >= now() - 7 days
            models.Index(fields=("location", "created_at"), name="locview_loc_created_idx"),
        ]


class LocationSubscription(models.Model):
    """Bonus: user gets an email about every new review on the location."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="subscriptions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="location_subscriptions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("location", "user"), name="subscription_unique"),
        ]
