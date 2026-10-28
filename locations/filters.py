import django_filters

from .models import Location


class LocationFilter(django_filters.FilterSet):
    rating_min = django_filters.NumberFilter(field_name="rating", lookup_expr="gte")
    rating_max = django_filters.NumberFilter(field_name="rating", lookup_expr="lte")

    class Meta:
        model = Location
        fields = ("category", "author")
