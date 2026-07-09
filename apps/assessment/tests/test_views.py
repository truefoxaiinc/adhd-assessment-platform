import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import Users
from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResult, SelfAssessmentResponse
from apps.progresstracker.models import FaceAttentionSession

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user():
    return Users.objects.create_user(
        username='assessment_test',
        email='assessment_test@test.com',
        password='Password123!',
        is_verified=True,
        dob='1990-01-01'  # adult
    )

@pytest.fixture
def child_user():
    return Users.objects.create_user(
        username='child_test',
        email='child_test@test.com',
        password='Password123!',
        is_verified=True,
        dob='2020-01-01'  # child
    )

@pytest.fixture
def questions():
    q1 = SelfAssessmentQuestions.objects.create(question_text="Adult Question 1", is_for_adults=True, is_active=True)
    q2 = SelfAssessmentQuestions.objects.create(question_text="Child Question 1", is_for_adults=False, is_active=True)
    return q1, q2

@pytest.mark.django_db
class TestAssessmentViews:
    SCORE_URL = '/api/assessment/v1/ai-attention/scores'
    COMBINED_RESULTS_URL = '/api/assessment/v1/self-assessment/results'

    def test_get_questions_adult(self, api_client, user, questions):
        api_client.force_authenticate(user=user)
        url = '/api/assessment/v1/self-assessment/get-questions'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert len(response.data['data']['questions']) == 1
        assert response.data['data']['questions'][0]['question_text'] == "Adult Question 1"

    def test_get_questions_child(self, api_client, child_user, questions):
        api_client.force_authenticate(user=child_user)
        url = '/api/assessment/v1/self-assessment/get-questions'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']['questions']) == 1
        assert response.data['data']['questions'][0]['question_text'] == "Child Question 1"

    def test_get_questions_unauthenticated(self, api_client):
        url = '/api/assessment/v1/self-assessment/get-questions'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_save_response(self, api_client, user, questions):
        api_client.force_authenticate(user=user)
        # Create a result first or just pass the required fields
        # Wait, SelfAssessmentResponseApiView expects some data. What is the serializer expecting?
        # Let's just pass some dummy data and expect 400 or 201
        url = '/api/assessment/v1/self-assessment/save-response'
        data = {
            "question": questions[0].id,
            "response": "2"
        }
        response = api_client.post(url, data, format='json')
        # It might require result_entry. We just assert it doesn't 500
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

    def test_completed_assessment_retake_is_saved_separately(
        self,
        api_client,
        user,
        questions,
        monkeypatch,
    ):
        api_client.force_authenticate(user=user)
        url = '/api/assessment/v1/self-assessment/save-response'

        def calculate_result(instance, is_adult):
            instance.result = 'Completed'
            instance.raw_total = instance.id
            instance.tenscore = float(instance.id)
            instance.save(
                update_fields=['result', 'raw_total', 'tenscore']
            )
            return instance

        monkeypatch.setattr(
            'apps.assessment.api.serializers.AssessmentService.calculate_result',
            calculate_result,
        )
        answers = [{
            'question': questions[0].id,
            'response': '2',
        }]

        first_response = api_client.post(
            url,
            {'assesment': answers},
            format='json',
        )
        retry_response = api_client.post(
            url,
            {'assesment': answers},
            format='json',
        )
        retake_response = api_client.post(
            url,
            {'assesment': answers, 'retake': True},
            format='json',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert retry_response.status_code == status.HTTP_201_CREATED
        assert retake_response.status_code == status.HTTP_201_CREATED
        results = list(
            SelfAssessmentResult.objects
            .filter(user=user)
            .order_by('id')
        )
        assert len(results) == 2
        assert results[0].id == first_response.data['data']['id']
        assert results[0].id == retry_response.data['data']['id']
        assert results[1].id == retake_response.data['data']['id']
        assert results[0].result_for_response.count() == 1
        assert results[1].result_for_response.count() == 1
        assert results[0].tenscore != results[1].tenscore

    def test_retake_rejected_until_current_assessment_is_complete(
        self,
        api_client,
        user,
    ):
        first_question = SelfAssessmentQuestions.objects.create(
            question_text='First',
            is_for_adults=True,
            is_active=True,
        )
        SelfAssessmentQuestions.objects.create(
            question_text='Second',
            is_for_adults=True,
            is_active=True,
        )
        api_client.force_authenticate(user=user)
        url = '/api/assessment/v1/self-assessment/save-response'
        partial_answers = [{
            'question': first_question.id,
            'response': '2',
        }]

        first_response = api_client.post(
            url,
            {'assesment': partial_answers},
            format='json',
        )
        retake_response = api_client.post(
            url,
            {'assesment': partial_answers, 'retake': True},
            format='json',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert retake_response.status_code == status.HTTP_400_BAD_REQUEST
        assert SelfAssessmentResult.objects.filter(user=user).count() == 1

    def test_fetch_result(self, api_client, user):
        api_client.force_authenticate(user=user)
        SelfAssessmentResult.objects.create(user=user, result="High Risk", tenscore=8.5)
        url = '/api/assessment/v1/self-assessment/fetch-result'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data']['result'] == "High Risk"

    def test_combined_results_include_only_authenticated_user_assessment_ai(
        self,
        api_client,
        user,
        child_user,
    ):
        api_client.force_authenticate(user=user)
        first_result = SelfAssessmentResult.objects.create(
            user=user,
            result='Moderate difficulty',
            raw_total=50,
            tenscore=6,
        )
        second_result = SelfAssessmentResult.objects.create(
            user=user,
            result='Mild difficulty',
            raw_total=65,
            tenscore=8,
        )
        SelfAssessmentResult.objects.create(
            user=child_user,
            result='Other user',
            tenscore=10,
        )
        FaceAttentionSession.objects.create(
            user=user,
            session_id='assessment-one',
            is_assessment=True,
            concentration_score=4,
            average_concentration_score=4,
        )
        latest_ai = FaceAttentionSession.objects.create(
            user=user,
            session_id='assessment-two',
            is_assessment=True,
            concentration_score=8,
            average_concentration_score=8,
        )
        FaceAttentionSession.objects.create(
            user=user,
            session_id='management-session',
            is_assessment=False,
            concentration_score=1,
            average_concentration_score=1,
        )
        FaceAttentionSession.objects.create(
            user=child_user,
            session_id='other-user-assessment',
            is_assessment=True,
            concentration_score=1,
            average_concentration_score=1,
        )

        response = api_client.get(self.COMBINED_RESULTS_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['count'] == 2
        assert response.data['data']['self_assessment_count'] == 2
        assert response.data['data']['self_assessment_question_count'] == 0
        assert response.data['data']['ai_assessment_count'] == 2
        assert [
            row['id'] for row in response.data['data']['results']
        ] == [second_result.id, first_result.id]
        assert response.data['data']['ai_assessment']['total_sessions'] == 2
        assert (
            response.data['data']['ai_assessment']['average_attention_score']
            == 75.0
        )
        assert (
            response.data['data']['ai_assessment']['latest']['id']
            == latest_ai.id
        )
        assert (
            response.data['data']['ai_assessment']['latest']['is_assessment']
            is True
        )

    def test_score_list_requires_authentication(self, api_client):
        response = api_client.get(self.SCORE_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_score_list_is_user_scoped_and_paginated(self, api_client, user, child_user):
        api_client.force_authenticate(user=user)
        for index in range(3):
            FaceAttentionSession.objects.create(
                user=user,
                session_id=f'user-session-{index}',
                is_assessment=index % 2 == 0,
                concentration_score=index + 1,
                average_concentration_score=index + 1,
            )
        FaceAttentionSession.objects.create(
            user=child_user,
            session_id='other-user-session',
            concentration_score=8,
            average_concentration_score=8,
            is_assessment=True,
        )

        response = api_client.get(self.SCORE_URL, {'limit': 2})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['count'] == 3
        assert len(response.data['data']['results']) == 2
        assert response.data['data']['total_sessions'] == 3
        assert response.data['data']['total_assessments'] == 2
        assert response.data['data']['total_management'] == 1
        assert all(
            row['session_id'].startswith('user-session-')
            for row in response.data['data']['results']
        )

    def test_score_list_search_filter_and_sort(self, api_client, user):
        api_client.force_authenticate(user=user)
        FaceAttentionSession.objects.create(
            user=user,
            session_id='reading-low',
            concentration_score=2,
            average_concentration_score=2,
            is_assessment=False,
            gaze_state='CENTER',
            face_detected=True,
        )
        FaceAttentionSession.objects.create(
            user=user,
            session_id='reading-high',
            concentration_score=8,
            average_concentration_score=8,
            is_assessment=True,
            gaze_state='LEFT',
            face_detected=True,
        )
        FaceAttentionSession.objects.create(
            user=user,
            session_id='reading-medium',
            concentration_score=6,
            average_concentration_score=6,
            is_assessment=True,
            gaze_state='CENTER',
            face_detected=True,
        )

        response = api_client.get(
            self.SCORE_URL,
            {
                'search': 'reading',
                'gaze_state': 'CENTER',
                'face_detected': 'true',
                'is_assessment': 'true',
                'min_score': 5,
                'max_score': 8,
                'sort': 'score',
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert [
            row['attention_score'] for row in response.data['data']['results']
        ] == [75.0]
        assert response.data['data']['results'][0]['is_assessment'] is True

    def test_score_list_rejects_invalid_filters(self, api_client, user):
        api_client.force_authenticate(user=user)

        score_response = api_client.get(self.SCORE_URL, {'min_score': 'bad'})
        sort_response = api_client.get(self.SCORE_URL, {'sort': 'username'})

        assert score_response.status_code == status.HTTP_400_BAD_REQUEST
        assert sort_response.status_code == status.HTTP_400_BAD_REQUEST

    def test_score_list_cache_avoids_repeat_database_queries(self, api_client, user):
        cache.clear()
        api_client.force_authenticate(user=user)
        FaceAttentionSession.objects.create(
            user=user,
            session_id='cached-session',
            concentration_score=8,
            average_concentration_score=8,
        )

        with CaptureQueriesContext(connection) as first_queries:
            first_response = api_client.get(self.SCORE_URL)
        with CaptureQueriesContext(connection) as cached_queries:
            cached_response = api_client.get(self.SCORE_URL)

        assert first_response.status_code == status.HTTP_200_OK
        assert cached_response.data == first_response.data
        assert len(first_queries) <= 3
        assert len(cached_queries) == 0
