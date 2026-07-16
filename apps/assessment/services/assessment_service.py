from apps.assessment.models import SelfAssessmentResult
from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResponse
from apps.assessment.services.scoring_service import ScoringService
from django.utils import timezone


class AssessmentService:
    @staticmethod
    def get_or_create_result_for_user(user):
        result = SelfAssessmentResult.objects.filter(user=user).order_by('-id').first()
        if result and result.completed_at is None:
            return result

        result = SelfAssessmentResult(user=user)
        result.save()
        return result

    @staticmethod
    def calculate_result(result, is_adult):
        completion = AssessmentService.get_completion_summary(result, is_adult)

        if not completion["is_complete"]:
            return result

        result = ScoringService.calculate_self_assessment(result, is_adult)
        if result.completed_at is None:
            result.completed_at = timezone.now()
            result.save(update_fields=['completed_at'])
        return result

    @staticmethod
    def get_completion_summary(result, is_adult):
        expected_question_ids = set(
            SelfAssessmentQuestions.objects.filter(
                is_for_adults=is_adult,
                is_active=True,
            ).values_list('id', flat=True)
        )
        answered_question_ids = set(
            SelfAssessmentResponse.objects.filter(
                result_entry=result,
                question_id__in=expected_question_ids,
            ).values_list('question_id', flat=True)
        )
        total_questions = len(expected_question_ids)
        answered_questions = len(answered_question_ids)
        pending_questions = max(total_questions - answered_questions, 0)
        completed_percentage = 0
        if total_questions:
            completed_percentage = round((answered_questions / total_questions) * 100, 2)

        return {
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "pending_questions": pending_questions,
            "completed_percentage": completed_percentage,
            "is_complete": bool(total_questions and answered_question_ids == expected_question_ids),
        }
