import django_filters

from .models import Location


class LocationFilter(django_filters.FilterSet):
    # `rating` is an annotation (see selectors), filtering on it works because
    # the viewset annotates the queryset before filter backends run.
    rating_min = django_filters.NumberFilter(field_name="rating", lookup_expr="gte")
    rating_max = django_filters.NumberFilter(field_name="rating", lookup_expr="lte")

    class Meta:
        model = Location
        # ModelChoiceFilter under the hood: unknown id -> 400 instead of empty list.
        fields = ("category", "author")
