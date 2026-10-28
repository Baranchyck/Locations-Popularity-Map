from django.db.models import F
from rest_framework.filters import OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    """
    OrderingFilter that
    * puts NULLs last in both directions (PostgreSQL puts NULLs FIRST on DESC,
      so `?ordering=-rating` would otherwise start with unrated locations);
    * appends `-pk` as a tie-breaker so pagination is deterministic
      (without a total order, rows with equal keys may jump between pages).
    """

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
