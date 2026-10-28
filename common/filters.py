from django.db.models import F
from rest_framework.filters import OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    """NULLs last in both directions + pk tie-breaker for stable pagination."""

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset

        expressions = []
        for field in ordering:
            if field.startswith("-"):
                expressions.append(F(field[1:]).desc(nulls_last=True))
            else:
                expressions.append(F(field).asc(nulls_last=True))
        expressions.append(F("pk").desc())
        return queryset.order_by(*expressions)
