from apps.assessment.models import SelfAssessmentResult
from apps.assessment.services.scoring_service import ScoringService


class AssessmentService:
    @staticmethod
    def get_or_create_result_for_user(user):
        result = SelfAssessmentResult.objects.filter(user=user).order_by('-id').first()
        if result:
            return result

        result = SelfAssessmentResult(user=user)
        result.save()
        return result

    @staticmethod
    def calculate_result(result, is_adult):
        return ScoringService.calculate_self_assessment(result, is_adult)
