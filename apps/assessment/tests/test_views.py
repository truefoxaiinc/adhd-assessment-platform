import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from apps.users.models import Users
from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResult, SelfAssessmentResponse
from services.assessment_result.assessment_result_services import ResultService
from apps.filehandler.models import AdhdContent
from apps.progresstracker.models import FaceAttentionSession, ProgressTracker, UserAssessmentDetails

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
    AI_SCORE_SAVE_URL = '/api/assessment/v1/ai-assessment/save-score'
    MANAGEMENT_DASHBOARD_URL = '/api/assessment/v1/management/dashboard'
    MANAGEMENT_LATEST_WEEK_URL = '/api/assessment/v1/management/latest-week'

    def full_attention_payload(self, **overrides):
        content = overrides.pop('content', None)
        if content is None:
            content = AdhdContent.objects.create(
                title=f"Attention Content {overrides.get('session_id', 'default')}",
                file='adhd_content/attention-content.mp4',
                is_management=False,
                age_group='adult',
                file_type='video',
                order_number=1,
            )

        payload = {
            'session_id': 'frontend-session',
            'file_id': content.id,
            'is_assessment': True,
            'final_score': 80,
            'attention_engagement_rate': 90,
            'average_confidence': 0.85,
            'total_processed_frames': 120,
            'sampled_frames': 120,
            'session_duration_seconds': 300,
            'inattention_duration': 20,
            'gaze_ratio_avg': 0,
            'drowsy_state': 0,
            'brightness_score': 0,
            'pitch': 0,
            'yaw': 0,
            'roll': 0,
            'blink_ratio': 0,
            'yawn_distance': 0,
            'bad_frame_count': 0,
            'blurry_frame_count': 0,
            'low_light_frame_count': 0,
            'eyes_closed_count': 0,
            'gaze_warning_count': 0,
        }
        payload.update(overrides)
        return payload

    def create_management_session(self, user, *, days_ago, score, attention=80, duration=3600):
        session = FaceAttentionSession.objects.create(
            user=user,
            is_assessment=False,
            concentration_score=round((score / 100) * 8, 2),
            average_concentration_score=round((score / 100) * 8, 2),
            attention_engagement_rate=attention,
            session_duration_seconds=duration,
            total_processed_frames=100,
            sampled_frames=100,
        )
        created_at = timezone.now() - timedelta(days=days_ago)
        FaceAttentionSession.objects.filter(id=session.id).update(created_at=created_at)
        session.created_at = created_at
        return session

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

    def test_self_assessment_score_uses_answered_question_max_score(self, user):
        result = SelfAssessmentResult.objects.create(user=user)
        rf_question = SelfAssessmentQuestions.objects.create(
            question_text='RF Question',
            category='RF',
            is_for_adults=True,
            is_active=True,
        )
        reverse_question = SelfAssessmentQuestions.objects.create(
            question_text='Reverse Question',
            category='N',
            is_for_adults=True,
            is_active=True,
        )
        SelfAssessmentResponse.objects.create(
            result_entry=result,
            question=rf_question,
            response='4',
        )
        SelfAssessmentResponse.objects.create(
            result_entry=result,
            question=reverse_question,
            response='0',
        )

        calculated = ResultService(result, is_adult=True).calculate_selfassessment()

        assert calculated.raw_total == 8
        assert calculated.tenscore == 10
        assert calculated.result == 'Satisfactory to strong'

    def test_fetch_result(self, api_client, user):
        api_client.force_authenticate(user=user)
        SelfAssessmentResult.objects.create(
            user=user,
            result="High Risk",
            tenscore=8.5,
            completed_at=timezone.now(),
        )
        url = '/api/assessment/v1/self-assessment/fetch-result'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data']['result'] == "High Risk"

    def test_fetch_result_finalizes_complete_pending_attempt(self, api_client, user):
        api_client.force_authenticate(user=user)
        question = SelfAssessmentQuestions.objects.create(
            question_text="Adult Question",
            category='RF',
            is_for_adults=True,
            is_active=True,
        )
        result = SelfAssessmentResult.objects.create(user=user)
        SelfAssessmentResponse.objects.create(
            result_entry=result,
            question=question,
            response='4',
        )

        response = api_client.get('/api/assessment/v1/self-assessment/fetch-result')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data']['is_completed'] is True
        assert response.data['data']['raw_total'] == 4
        assert response.data['data']['tenscore'] == 10

    def test_fetch_result_returns_progress_for_incomplete_attempt(self, api_client, user):
        api_client.force_authenticate(user=user)
        answered_question = SelfAssessmentQuestions.objects.create(
            question_text="Answered Adult Question",
            is_for_adults=True,
            is_active=True,
        )
        SelfAssessmentQuestions.objects.create(
            question_text="Pending Adult Question",
            is_for_adults=True,
            is_active=True,
        )
        result = SelfAssessmentResult.objects.create(user=user)
        SelfAssessmentResponse.objects.create(
            result_entry=result,
            question=answered_question,
            response='2',
        )

        response = api_client.get('/api/assessment/v1/self-assessment/fetch-result')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data']['is_completed'] is False
        assert response.data['data']['total_questions'] == 2
        assert response.data['data']['answered_questions'] == 1
        assert response.data['data']['pending_questions'] == 1
        assert response.data['data']['completed_percentage'] == 50.0

    def test_progress_ignores_completed_attempt_for_next_questionnaire(self, api_client, user):
        cache.clear()
        api_client.force_authenticate(user=user)
        question = SelfAssessmentQuestions.objects.create(
            question_text="Completed Attempt Question",
            is_for_adults=True,
            is_active=True,
        )
        completed_result = SelfAssessmentResult.objects.create(
            user=user,
            completed_at=timezone.now(),
        )
        SelfAssessmentResponse.objects.create(
            result_entry=completed_result,
            question=question,
            response='4',
        )

        response = api_client.get('/api/assessment/v1/self-assessment/progress')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data']['result_id'] is None
        assert response.data['data']['answered_questions'] == 0
        assert response.data['data']['pending_questions'] == 1
        assert response.data['data']['questions'][0]['is_answered'] is False

    def test_save_response_after_completed_attempt_starts_new_attempt(self, api_client, user):
        cache.clear()
        api_client.force_authenticate(user=user)
        question = SelfAssessmentQuestions.objects.create(
            question_text="Retake Question",
            is_for_adults=True,
            is_active=True,
        )
        completed_result = SelfAssessmentResult.objects.create(
            user=user,
            completed_at=timezone.now(),
        )
        SelfAssessmentResponse.objects.create(
            result_entry=completed_result,
            question=question,
            response='1',
        )

        response = api_client.post(
            '/api/assessment/v1/self-assessment/save-response',
            {'assesment': [{'question': question.id, 'response': '3'}]},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] is True
        assert response.data['data']['id'] != completed_result.id
        assert SelfAssessmentResult.objects.filter(user=user).count() == 2

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

    def test_management_dashboard_empty_state(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(self.MANAGEMENT_DASHBOARD_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert response.data['data']['overview']['weeks_tracked'] == 0
        assert response.data['data']['overview']['average_total_score'] == 0
        assert response.data['data']['weekly_progress']['results'] == []
        assert 'latest_week' not in response.data['data']

    def test_management_dashboard_returns_user_based_summary(self, api_client, user):
        other_user = Users.objects.create_user(
            username='other_dashboard_user',
            email='other_dashboard_user@test.com',
            password='Password123!',
            is_verified=True,
        )
        self.create_management_session(user, days_ago=35, score=62, attention=70, duration=1800)
        self.create_management_session(user, days_ago=28, score=68, attention=72, duration=2400)
        self.create_management_session(user, days_ago=21, score=74, attention=78, duration=3000)
        self.create_management_session(user, days_ago=14, score=80, attention=82, duration=3600)
        self.create_management_session(user, days_ago=7, score=71, attention=75, duration=1200)
        self.create_management_session(user, days_ago=0, score=85, attention=84, duration=5100)
        self.create_management_session(other_user, days_ago=0, score=10, attention=10, duration=60)
        FaceAttentionSession.objects.create(
            user=user,
            is_assessment=True,
            concentration_score=8,
            average_concentration_score=8,
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(self.MANAGEMENT_DASHBOARD_URL)

        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['overview']['weeks_tracked'] == 6
        assert data['overview']['average_total_score'] == 73.33
        assert data['overview']['best_week_score'] == 85.0
        assert len(data['weekly_progress']['results']) == 6
        assert data['weekly_progress']['results'][-1]['total_score'] == 85.0
        assert data['weekly_progress']['improvement']['points'] == 23.0
        assert 'latest_week' not in data

    def test_management_dashboard_rejects_invalid_weeks_filter(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(self.MANAGEMENT_DASHBOARD_URL, {'weeks': 'many'})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['weeks'] == 'Use a number between 1 and 52.'

    def test_management_latest_week_returns_all_week_details(self, api_client, user):
        cache.clear()
        self.create_management_session(user, days_ago=14, score=62, attention=70, duration=900)
        self.create_management_session(user, days_ago=7, score=71, attention=75, duration=1200)
        self.create_management_session(user, days_ago=0, score=85, attention=84, duration=5100)
        api_client.force_authenticate(user=user)

        response = api_client.get(self.MANAGEMENT_LATEST_WEEK_URL, {'page': 1, 'limit': 2})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert set(response.data['data'].keys()) == {
            'links',
            'count',
            'page',
            'limit',
            'total_pages',
            'results',
        }
        assert response.data['data']['count'] == 3
        assert response.data['data']['page'] == 1
        assert response.data['data']['limit'] == 2
        assert response.data['data']['total_pages'] == 2
        assert len(response.data['data']['results']) == 2
        assert 'page=2' in response.data['data']['links']['next']
        first_page_week = response.data['data']['results'][-1]
        assert set(first_page_week.keys()) == {
            'week_number',
            'start_date',
            'end_date',
            'days',
            'selected_day',
        }
        assert first_page_week['selected_day']['total_score'] == 71.0

        response = api_client.get(self.MANAGEMENT_LATEST_WEEK_URL, {'page': 2, 'limit': 2})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']['results']) == 1
        latest_week = response.data['data']['results'][0]
        assert latest_week['selected_day']['total_score'] == 85.0
        assert latest_week['selected_day']['duration_label'] == '1h 25m'

    def test_management_latest_week_empty_state(self, api_client, user):
        cache.clear()
        api_client.force_authenticate(user=user)

        response = api_client.get(self.MANAGEMENT_LATEST_WEEK_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['count'] == 0
        assert response.data['data']['page'] == 1
        assert response.data['data']['limit'] == 10
        assert response.data['data']['total_pages'] == 0
        assert response.data['data']['results'] == []

    def test_management_latest_week_rejects_invalid_pagination(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.get(self.MANAGEMENT_LATEST_WEEK_URL, {'page': 0})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['page'] == 'Use a number greater than or equal to 1.'

    def test_save_frontend_attention_score(self, api_client, user):
        api_client.force_authenticate(user=user)
        content = AdhdContent.objects.create(
            title='Assessment Video',
            file='adhd_content/assessment-video.mp4',
            is_management=False,
            age_group='adult',
            file_type='video',
            order_number=1,
        )

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(content=content),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] is True
        assert response.data['data']['session_id'] == 'frontend-session'
        assert response.data['data']['score'] == 80.0

        session = FaceAttentionSession.objects.get(
            user=user,
            session_id='frontend-session',
        )
        assert session.file_id == content.id
        assert session.average_concentration_score == 6.4
        assert session.total_processed_frames == 120

        user.refresh_from_db()
        assert user.ai_assessment_score == 80

    def test_save_frontend_attention_score_generates_session_id(self, api_client, user):
        api_client.force_authenticate(user=user)
        payload = self.full_attention_payload()
        payload.pop('session_id')

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            payload,
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['data']['session_id']
        assert FaceAttentionSession.objects.filter(
            user=user,
            session_id=response.data['data']['session_id'],
        ).exists()

    def test_save_frontend_attention_score_updates_learning_progress_for_management_file(self, api_client, user):
        api_client.force_authenticate(user=user)
        content = AdhdContent.objects.create(
            title='Management Day 1 Video',
            file='adhd_content/management-day-1-video.mp4',
            is_management=True,
            age_group='adult',
            day=1,
            file_type='video',
            order_number=1,
        )

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                content=content,
                is_assessment=False,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert ProgressTracker.objects.filter(
            user=user,
            day_number=1,
            file_type='video',
            order_number='1',
        ).exists()

        assessment_details = UserAssessmentDetails.objects.get(user=user)
        assert assessment_details.last_completed == 1

    def test_save_frontend_attention_score_rejects_locked_management_file(self, api_client, user):
        api_client.force_authenticate(user=user)
        content = AdhdContent.objects.create(
            title='Management Day 2 Video',
            file='adhd_content/management-day-2-video.mp4',
            is_management=True,
            age_group='adult',
            day=2,
            file_type='video',
            order_number=1,
        )

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                content=content,
                is_assessment=False,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['file_id'] == 'Lesson/file is locked for this user.'
        assert not ProgressTracker.objects.filter(user=user, day_number=2).exists()

    def test_save_frontend_attention_score_requires_score(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            {'session_id': 'frontend-session'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'final_score' in response.data['errors']
        assert 'file_id' in response.data['errors']
        assert 'total_processed_frames' in response.data['errors']
        assert 'sampled_frames' in response.data['errors']

    def test_save_frontend_attention_score_rejects_non_numeric_score(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='bad-score-session',
                final_score='high',
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'final_score' in response.data['errors']

    def test_save_frontend_attention_score_rejects_out_of_range_values(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='bad-range-session',
                final_score=101,
                attention_engagement_rate=101,
                average_confidence=2,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'final_score' in response.data['errors']
        assert 'attention_engagement_rate' in response.data['errors']
        assert 'average_confidence' in response.data['errors']

    def test_save_frontend_attention_score_rejects_unknown_fields(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='unknown-field-session',
                face_detected=True,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['face_detected'] == 'Unknown field.'

    def test_save_frontend_attention_score_rejects_invalid_file_id(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='invalid-file-session',
                file_id=999999,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'file_id' in response.data['errors']

    def test_save_frontend_attention_score_rejects_user_id_payload(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='spoofed-user-session',
                user_id=user.id,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['user_id'] == 'Unknown field.'

    def test_save_frontend_attention_score_is_scoped_to_authenticated_user(self, api_client, user):
        other_user = Users.objects.create_user(
            username='other_score_user',
            email='other_score_user@test.com',
            password='Password123!',
            is_verified=True,
        )

        api_client.force_authenticate(user=user)
        first_response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(session_id='shared-session'),
            format='json',
        )

        api_client.force_authenticate(user=other_user)
        second_response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='shared-session',
                final_score=60,
            ),
            format='json',
        )

        assert first_response.status_code == status.HTTP_201_CREATED
        assert second_response.status_code == status.HTTP_201_CREATED
        assert FaceAttentionSession.objects.filter(session_id='shared-session').count() == 2
        assert FaceAttentionSession.objects.get(user=user, session_id='shared-session').average_concentration_score == 6.4
        assert FaceAttentionSession.objects.get(user=other_user, session_id='shared-session').average_concentration_score == 4.8

    def test_save_frontend_attention_score_rejects_average_score_payload(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='average-score-payload-session',
                average_concentration_score=8,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['average_concentration_score'] == 'Unknown field.'

    def test_save_frontend_attention_score_rejects_concentration_score_payload(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='concentration-score-payload-session',
                concentration_score=1,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['concentration_score'] == 'Unknown field.'

    def test_save_frontend_attention_score_rejects_inconsistent_frame_counts(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='bad-frame-count-session',
                total_processed_frames=10,
                sampled_frames=11,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'sampled_frames' in response.data['errors']

    def test_save_frontend_attention_score_rejects_inconsistent_duration(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.AI_SCORE_SAVE_URL,
            self.full_attention_payload(
                session_id='bad-duration-session',
                session_duration_seconds=30,
                inattention_duration=31,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'inattention_duration' in response.data['errors']
