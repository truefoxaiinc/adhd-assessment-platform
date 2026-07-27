from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.assessment.cache import bump_user_management_cache
from apps.progresstracker.models import (
    FaceAttentionSession,
    ManagementActivitySession,
    ProgressTracker,
    UserAssessmentDetails,
)


def _bump_user_cache(instance):
    bump_user_management_cache(getattr(instance, 'user_id', None))


@receiver(post_save, sender=FaceAttentionSession)
@receiver(post_delete, sender=FaceAttentionSession)
def clear_management_cache_on_attention_session_change(sender, instance, **kwargs):
    _bump_user_cache(instance)


@receiver(post_save, sender=ManagementActivitySession)
@receiver(post_delete, sender=ManagementActivitySession)
def clear_management_cache_on_activity_session_change(sender, instance, **kwargs):
    _bump_user_cache(instance)


@receiver(post_save, sender=ProgressTracker)
@receiver(post_delete, sender=ProgressTracker)
def clear_management_cache_on_progress_change(sender, instance, **kwargs):
    _bump_user_cache(instance)


@receiver(post_save, sender=UserAssessmentDetails)
@receiver(post_delete, sender=UserAssessmentDetails)
def clear_management_cache_on_assessment_details_change(sender, instance, **kwargs):
    _bump_user_cache(instance)
