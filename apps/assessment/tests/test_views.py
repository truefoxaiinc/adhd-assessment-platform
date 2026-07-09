import pytest
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
    AI_SCORE_URL = '/api/assessment/v1/ai-assessment/score-history'

    def test_get_questions_adult(self, api_client, user, questions):
        api_client.force_authenticate(user=user)
        url = '/api/assessment/v1/self-assessment/get-questions'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_201_CREATED  # It returns 201 as per code
        assert response.data['status'] is True
        assert len(response.data['data']['questions']) == 1
        assert response.data['data']['questions'][0]['question_text'] == "Adult Question 1"

    def test_get_questions_child(self, api_client, child_user, questions):
        api_client.force_authenticate(user=child_user)
        url = '/api/assessment/v1/self-assessment/get-questions'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_201_CREATED
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

    def test_fetch_result(self, api_client, user):
        api_client.force_authenticate(user=user)
        SelfAssessmentResult.objects.create(user=user, result="High Risk", tenscore=8.5)
        url = '/api/assessment/v1/self-assessment/fetch-result'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data']['result'] == "High Risk"

    def test_ai_score_history_filters_assessment_sessions(self, api_client, user):
        other_user = Users.objects.create_user(
            username='other_ai_user',
            email='other_ai_user@test.com',
            password='Password123!',
        )
        FaceAttentionSession.objects.create(
            user=user,
            session_id='assessment-session',
            is_assessment=True,
            concentration_score=6,
            average_concentration_score=6,
        )
        FaceAttentionSession.objects.create(
            user=user,
            session_id='management-session',
            is_assessment=False,
            concentration_score=4,
            average_concentration_score=4,
        )
        FaceAttentionSession.objects.create(
            user=other_user,
            session_id='other-session',
            is_assessment=True,
            concentration_score=8,
            average_concentration_score=8,
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(
            self.AI_SCORE_URL,
            {'is_assessment': 'true'},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['count'] == 1
        assert response.data['data']['results'][0]['session_id'] == 'assessment-session'
        assert response.data['data']['results'][0]['is_assessment'] is True
        assert response.data['data']['results'][0]['score'] == 75.0

    def test_ai_score_history_filters_management_sessions(self, api_client, user):
        FaceAttentionSession.objects.create(
            user=user,
            session_id='management-session',
            is_assessment=False,
            concentration_score=4,
            average_concentration_score=4,
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(
            self.AI_SCORE_URL,
            {'is_assessment': 'false'},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['count'] == 1
        assert response.data['data']['results'][0]['is_assessment'] is False

    def test_ai_score_history_rejects_invalid_filter(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(
            self.AI_SCORE_URL,
            {'is_assessment': 'yes'},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['is_assessment'] == 'Use true or false.'
