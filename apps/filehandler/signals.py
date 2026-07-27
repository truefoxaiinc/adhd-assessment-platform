from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.assessment.cache import bump_global_management_cache
from apps.filehandler.models import AdhdContent


@receiver(post_save, sender=AdhdContent)
@receiver(post_delete, sender=AdhdContent)
def clear_management_cache_on_content_change(sender, instance, **kwargs):
    if instance.is_management:
        bump_global_management_cache()
