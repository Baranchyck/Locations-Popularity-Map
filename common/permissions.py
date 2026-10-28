from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    """Anyone can read; only staff can write."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(request.user and request.user.is_staff)


class IsAuthorOrAdminOrReadOnly(BasePermission):
    """
    Read: anyone. Create: authenticated. Update/delete: the object's author or staff.
    Expects the object to have an `author_id` attribute.
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(
            request.user and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff or obj.author_id == request.user.id
