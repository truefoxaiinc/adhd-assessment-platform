from django.db.models import Q

from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResponse, SelfAssessmentResult


def get_active_questions_for_user_type(is_for_adults):
    return (
        SelfAssessmentQuestions.objects
        .filter(Q(is_for_adults=is_for_adults) & Q(is_active=True))
        .only('id', 'question_text', 'category', 'is_for_adults', 'is_active')
        .order_by('-id')
    )


def get_latest_result_for_user(user):
    return SelfAssessmentResult.objects.filter(user=user).order_by('-id').first()


def get_responses_for_result(result, question_ids):
    return SelfAssessmentResponse.objects.filter(
        result_entry=result,
        question_id__in=question_ids,
    )
