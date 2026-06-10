from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import QUESTIONS_CACHE_VERSION_KEY, bump_cache_version, bump_user_result_cache
from .models import SelfAssessmentQuestions, SelfAssessmentResponse, SelfAssessmentResult


@receiver(post_save, sender=SelfAssessmentQuestions)
@receiver(post_delete, sender=SelfAssessmentQuestions)
def clear_questions_cache(sender, instance, **kwargs):
    bump_cache_version(QUESTIONS_CACHE_VERSION_KEY)


@receiver(post_save, sender=SelfAssessmentResult)
@receiver(post_delete, sender=SelfAssessmentResult)
def clear_result_cache(sender, instance, **kwargs):
    bump_user_result_cache(instance.user_id)


@receiver(post_save, sender=SelfAssessmentResponse)
@receiver(post_delete, sender=SelfAssessmentResponse)
def clear_response_result_cache(sender, instance, **kwargs):
    if instance.result_entry_id:
        bump_user_result_cache(instance.result_entry.user_id)
