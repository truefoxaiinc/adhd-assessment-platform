from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.assessment.cache import bump_global_management_cache, bump_user_management_cache
from apps.filehandler.models import AdhdContent, ContentAttempt, ContentQuestion, QuestionOption


@receiver(post_save, sender=AdhdContent)
@receiver(post_delete, sender=AdhdContent)
def clear_management_cache_on_content_change(sender, instance, **kwargs):
    if instance.is_management:
        bump_global_management_cache()


@receiver(post_save, sender=ContentQuestion)
@receiver(post_delete, sender=ContentQuestion)
def clear_management_cache_on_question_change(sender, instance, **kwargs):
    if instance.content.is_management:
        bump_global_management_cache()


@receiver(post_save, sender=QuestionOption)
@receiver(post_delete, sender=QuestionOption)
def clear_management_cache_on_option_change(sender, instance, **kwargs):
    if instance.question.content.is_management:
        bump_global_management_cache()


@receiver(post_save, sender=ContentAttempt)
@receiver(post_delete, sender=ContentAttempt)
def clear_management_cache_on_attempt_change(sender, instance, **kwargs):
    if instance.content.is_management:
        bump_user_management_cache(instance.user_id)
