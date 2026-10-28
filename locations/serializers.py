from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Category, Location

User = get_user_model()


class UserShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "description", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate_name(self, value: str) -> str:
        # The DB has a functional UniqueConstraint(Lower("name")); DRF doesn't
        # derive validators from expression constraints, so check explicitly.
        value = value.strip()
        qs = Category.objects.filter(name__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value


class LocationSerializer(serializers.ModelSerializer):
    author = UserShortSerializer(read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source="category.name", read_only=True)

    # Computed by the DB (selectors.annotate_location_stats), never stored.
    rating = serializers.SerializerMethodField()
    reviews_count = serializers.IntegerField(read_only=True)
    views_7d = serializers.IntegerField(read_only=True)
    popularity = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = (
            "id",
            "name",
            "description",
            "category",
            "category_name",
            "address",
            "latitude",
            "longitude",
            "author",
            "rating",
            "reviews_count",
            "views_7d",
            "popularity",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_rating(self, obj) -> float | None:
        return None if obj.rating is None else round(obj.rating, 2)

    def get_popularity(self, obj) -> float:
        return round(obj.popularity, 3)
