from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import bump_list_version
from .models import Category, Location, Review


@receiver([post_save, post_delete], sender=Location)
@receiver([post_save, post_delete], sender=Review)
@receiver([post_save, post_delete], sender=Category)
def invalidate_location_list(sender, **kwargs):
    # Soft delete is a save(), so post_save covers it too.
    transaction.on_commit(bump_list_version)
