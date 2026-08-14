from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.filehandler.models import (
    AdhdContent,
    AttemptStatus,
    ContentAnswer,
    ContentAttempt,
    ContentStatus,
    QuestionType,
)
from apps.payments.selectors import user_has_active_subscription
from apps.progresstracker.models import FaceAttentionSession, ProgressTracker, UserAssessmentDetails
from apps.progresstracker.services.track_services import ProgressTrackerActions


class LearningContentService:
    PASS_PERCENTAGE = 60.0

    @staticmethod
    def user_age_group(user):
        return user.age_category or 'adult'

    @classmethod
    def unlocked_days(cls, user):
        return ProgressTrackerActions.get_days_for_the_file(user) or [1]

    @classmethod
    def is_locked(cls, content, user, unlocked_days=None):
        if not content.is_management:
            return False
        unlocked_days = unlocked_days or cls.unlocked_days(user)
        return content.day not in unlocked_days

    @classmethod
    def locked_reason(cls, content, user, unlocked_days=None):
        if not cls.is_locked(content, user, unlocked_days):
            return None
        if content.day and content.day > 1 and not user_has_active_subscription(user):
            return 'An active subscription is required for Day 2 and later.'
        return f'Complete the previous day to unlock Day {content.day}.'

    @classmethod
    def accessible_content(cls, content_id, user, *, allow_locked=False):
        content = (
            AdhdContent.objects
            .prefetch_related('questions__options')
            .filter(
                pk=content_id,
                status=ContentStatus.PUBLISHED,
                age_group=cls.user_age_group(user),
            )
            .first()
        )
        if content is None:
            raise ValidationError({'content_id': 'Content does not exist or is not available for this user.'})
        if not allow_locked and cls.is_locked(content, user):
            raise PermissionDenied(cls.locked_reason(content, user))
        return content

    @staticmethod
    def validate_question_configuration(content):
        errors = {}
        for question in content.questions.filter(is_active=True).prefetch_related('options'):
            options = list(question.options.all())
            correct_count = sum(option.is_correct for option in options)
            if len(options) < 2:
                errors[str(question.id)] = 'Question must have at least two options.'
            elif question.question_type in (QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE) and correct_count != 1:
                errors[str(question.id)] = 'Question must have exactly one correct option.'
            elif question.question_type == QuestionType.MULTIPLE_CHOICE and correct_count < 1:
                errors[str(question.id)] = 'Question must have at least one correct option.'
        if errors:
            raise ValidationError({'questions': errors})

    @classmethod
    def start_attempt(cls, user, content):
        cls.validate_question_configuration(content)
        existing = ContentAttempt.objects.filter(
            user=user,
            content=content,
            status=AttemptStatus.IN_PROGRESS,
        ).first()
        if existing:
            return existing, False

        with transaction.atomic():
            AdhdContent.objects.select_for_update().get(pk=content.pk)
            last_number = (
                ContentAttempt.objects
                .filter(user=user, content=content)
                .aggregate(value=Max('attempt_number'))['value']
                or 0
            )
            try:
                attempt = ContentAttempt.objects.create(
                    user=user,
                    content=content,
                    attempt_number=last_number + 1,
                )
            except IntegrityError:
                attempt = ContentAttempt.objects.get(
                    user=user,
                    content=content,
                    attempt_number=last_number + 1,
                )
        return attempt, True

    @classmethod
    def submit_content_once(cls, user, content, attention_session_id, submitted_answers):
        with transaction.atomic():
            locked_content = AdhdContent.objects.select_for_update().get(pk=content.pk)
            if ContentAttempt.objects.filter(
                user=user,
                content=locked_content,
                status=AttemptStatus.COMPLETED,
            ).exists():
                raise ValidationError({
                    'content_id': 'You have already submitted answers for this content.'
                })

            attention_session = (
                FaceAttentionSession.objects
                .select_for_update()
                .filter(
                    pk=attention_session_id,
                    user=user,
                    file=locked_content,
                    is_assessment=False,
                )
                .first()
            )
            if attention_session is None:
                raise ValidationError({
                    'face_attention_session_id': (
                        'Attention session does not exist or does not belong to this user and content.'
                    )
                })
            if ContentAttempt.objects.filter(attention_session=attention_session).exists():
                raise ValidationError({
                    'face_attention_session_id': 'This attention session already has a question result.'
                })

            attempt, created = cls.start_attempt(user, locked_content)
            attempt.attention_session = attention_session
            attempt.save(update_fields=['attention_session'])
            attempt, submitted = cls.submit_attempt(
                user,
                attempt.id,
                submitted_answers,
            )
            return attempt, created, submitted

    @classmethod
    def submit_attempt(cls, user, attempt_id, submitted_answers):
        with transaction.atomic():
            attempt = (
                ContentAttempt.objects
                .select_for_update()
                .select_related('content')
                .filter(pk=attempt_id, user=user)
                .first()
            )
            if attempt is None:
                raise ValidationError({'attempt_id': 'Attempt does not exist.'})
            if attempt.status == AttemptStatus.COMPLETED:
                return attempt, False
            if attempt.status != AttemptStatus.IN_PROGRESS:
                raise ValidationError({'attempt_id': 'Only an in-progress attempt can be submitted.'})
            if cls.is_locked(attempt.content, user):
                raise PermissionDenied(cls.locked_reason(attempt.content, user))

            questions = list(
                attempt.content.questions
                .filter(is_active=True)
                .prefetch_related('options')
                .order_by('display_order', 'id')
            )
            cls.validate_question_configuration(attempt.content)
            question_map = {question.id: question for question in questions}
            submitted_map = {answer['question_id']: answer for answer in submitted_answers}
            unknown_ids = sorted(set(submitted_map) - set(question_map))
            if unknown_ids:
                raise ValidationError({'answers': f'Questions do not belong to this content: {unknown_ids}.'})
            missing_ids = [question.id for question in questions if question.is_required and question.id not in submitted_map]
            if missing_ids:
                raise ValidationError({'answers': f'Required questions are missing: {missing_ids}.'})
            if not questions and submitted_answers:
                raise ValidationError({'answers': 'This content has no questions.'})

            total_score = 0.0
            maximum_score = float(sum(question.maximum_score for question in questions))
            for question in questions:
                submitted = submitted_map.get(question.id)
                if submitted is None:
                    continue
                options = {option.id: option for option in question.options.all()}
                selected_ids = set(submitted['selected_option_ids'])
                invalid_ids = sorted(selected_ids - set(options))
                if invalid_ids:
                    raise ValidationError({'answers': f'Invalid options for question {question.id}: {invalid_ids}.'})
                if question.question_type in (QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE) and len(selected_ids) != 1:
                    raise ValidationError({'answers': f'Question {question.id} requires exactly one option.'})

                correct_ids = {option.id for option in options.values() if option.is_correct}
                is_correct = selected_ids == correct_ids
                awarded_score = float(question.maximum_score if is_correct else 0)
                answer = ContentAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    is_correct=is_correct,
                    awarded_score=awarded_score,
                )
                answer.selected_options.set(selected_ids)
                total_score += awarded_score

            percentage = round((total_score / maximum_score) * 100, 2) if maximum_score else 100.0
            attempt.score = total_score
            attempt.maximum_score = maximum_score
            attempt.percentage = percentage
            attempt.passed = percentage >= cls.PASS_PERCENTAGE
            attempt.status = AttemptStatus.COMPLETED
            attempt.completed_at = timezone.now()
            attempt.save(update_fields=['score', 'maximum_score', 'percentage', 'passed', 'status', 'completed_at'])
            cls._record_progress(user, attempt.content, attempt.completed_at)
        return attempt, True

    @classmethod
    def _record_progress(cls, user, content, completed_at):
        ProgressTracker.objects.update_or_create(
            user=user,
            day_number=content.day,
            file_type=content.file_type,
            order_number=str(content.order_number),
            defaults={'is_day_completed': False},
        )
        if not content.is_management or not content.day:
            return

        required_content_ids = set(
            AdhdContent.objects.filter(
                is_management=True,
                status=ContentStatus.PUBLISHED,
                age_group=content.age_group,
                day=content.day,
            ).values_list('id', flat=True)
        )
        completed_content_ids = set(
            ContentAttempt.objects.filter(
                user=user,
                content_id__in=required_content_ids,
                status=AttemptStatus.COMPLETED,
            ).values_list('content_id', flat=True)
        )
        day_completed = bool(required_content_ids) and required_content_ids.issubset(completed_content_ids)
        ProgressTracker.objects.filter(user=user, day_number=content.day).update(is_day_completed=day_completed)
        details, _ = UserAssessmentDetails.objects.get_or_create(user=user)
        details.is_day_completed = day_completed
        if day_completed and content.day >= int(details.last_completed or 0):
            details.last_completed = content.day
            details.last_completed_at = completed_at
        details.save(update_fields=['is_day_completed', 'last_completed', 'last_completed_at'])
