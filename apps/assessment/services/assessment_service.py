from rest_framework.exceptions import ValidationError

from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResult
from apps.assessment.services.scoring_service import ScoringService


class AssessmentService:
    @staticmethod
    def get_or_create_result_for_user(user, is_adult, retake=False):
        result = SelfAssessmentResult.objects.filter(user=user).order_by('-id').first()
        if not result:
            return SelfAssessmentResult.objects.create(user=user)

        if not retake:
            return result

        if not AssessmentService.is_result_complete(result, is_adult):
            raise ValidationError({
                'retake': 'Complete the current assessment before starting a retake.'
            })

        return SelfAssessmentResult.objects.create(user=user)

    @staticmethod
    def is_result_complete(result, is_adult):
        active_question_ids = SelfAssessmentQuestions.objects.filter(
            is_for_adults=is_adult,
            is_active=True,
        ).values('id')
        total_questions = active_question_ids.count()
        if total_questions == 0:
            return False

        answered_questions = (
            result.result_for_response
            .filter(question_id__in=active_question_ids)
            .values('question_id')
            .distinct()
            .count()
        )
        return answered_questions >= total_questions

    @staticmethod
    def calculate_result(result, is_adult):
        return ScoringService.calculate_self_assessment(result, is_adult)
