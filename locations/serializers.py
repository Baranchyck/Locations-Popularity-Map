from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Category, Location, Review, ReviewVote

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


class ReviewSerializer(serializers.ModelSerializer):
    author = UserShortSerializer(read_only=True)
    likes = serializers.IntegerField(read_only=True)
    dislikes = serializers.IntegerField(read_only=True)
    my_vote = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "location",
            "author",
            "rating",
            "text",
            "likes",
            "dislikes",
            "my_vote",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("location", "created_at", "updated_at")


class VoteSerializer(serializers.Serializer):
    value = serializers.ChoiceField(
        choices=ReviewVote.Value.choices,
        help_text="1 = like, -1 = dislike",
    )
