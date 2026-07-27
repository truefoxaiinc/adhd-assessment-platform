from django.db.models import Q

from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResponse, SelfAssessmentResult


def normalize_assessment_age_group(age_group):
    if age_group is True:
        return 'adult'
    if age_group is False or age_group is None:
        return 'child'
    if age_group not in ('child', 'adolescents', 'adult'):
        return 'adult'
    return age_group


def get_active_questions_for_user_type(age_group):
    age_group = normalize_assessment_age_group(age_group)
    return (
        SelfAssessmentQuestions.objects
        .filter(Q(age_group=age_group) & Q(is_active=True))
        .only('id', 'question_text', 'category', 'age_group', 'is_for_adults', 'is_active')
        .order_by('-id')
    )


def get_latest_result_for_user(user):
    return SelfAssessmentResult.objects.filter(user=user).order_by('-id').first()


def get_responses_for_result(result, question_ids):
    return SelfAssessmentResponse.objects.filter(
        result_entry=result,
        question_id__in=question_ids,
    )
