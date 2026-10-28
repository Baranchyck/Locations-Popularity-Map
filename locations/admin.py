from django.contrib import admin

from .cache import bump_list_version
from .models import Category, Location, LocationSubscription, LocationView, Review, ReviewVote


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "category")
    search_fields = ("name", "description", "address")
    list_select_related = ("category", "author")
    readonly_fields = ("is_deleted", "deleted_at", "created_at", "updated_at")
    actions = ("restore_selected",)

    def get_queryset(self, request):
        # Admin sees soft-deleted rows too (the default manager hides them).
        return Location.all_objects.select_related("category", "author")

    @admin.action(description="Restore selected locations")
    def restore_selected(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)
        # QuerySet.update() doesn't send post_save -> invalidate explicitly.
        bump_list_version()


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "author", "rating", "created_at")
    list_filter = ("rating",)
    list_select_related = ("location", "author")


@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "user", "value", "created_at")


@admin.register(LocationView)
class LocationViewAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "user", "created_at")
    list_select_related = ("location", "user")


@admin.register(LocationSubscription)
class LocationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "user", "created_at")
