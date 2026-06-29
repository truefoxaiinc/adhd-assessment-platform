from services.assessment_result.assessment_result_services import ResultService


class ScoringService:
    @staticmethod
    def calculate_self_assessment(result, is_adult):
        return ResultService(result, is_adult).calculate_selfassessment()
