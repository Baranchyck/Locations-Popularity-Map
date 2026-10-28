from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import bump_list_version
from .models import Category, Location, Review


@receiver([post_save, post_delete], sender=Location)
@receiver([post_save, post_delete], sender=Review)
@receiver([post_save, post_delete], sender=Category)  # category_name is in the list
def invalidate_location_list(sender, **kwargs):
    # on_commit: if we bumped inside the transaction, a parallel request could
    # re-cache the *old* data between the bump and the COMMIT.
    # Soft delete goes through save() -> covered by post_save.
    transaction.on_commit(bump_list_version)
