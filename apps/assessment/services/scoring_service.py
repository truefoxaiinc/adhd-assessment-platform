from services.assessment_result.assessment_result_services import ResultService


class ScoringService:
    @staticmethod
    def calculate_self_assessment(result, age_group):
        return ResultService(result, age_group=age_group).calculate_selfassessment()
