import pytest
from django.contrib import admin
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APIClient

from apps.filehandler.models import (
    AdhdContent,
    ContentAttempt,
    ContentQuestion,
    ContentStatus,
    QuestionOption,
)
from apps.filehandler.admin import AdhdContentAdmin
from apps.progresstracker.models import ProgressTracker, UserAssessmentDetails
from apps.users.models import Users


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    user = Users.objects.create_user(
        username='learning_user',
        email='learning_user@test.com',
        password='Password123!',
        dob='1990-01-01',
        is_verified=True,
    )
    user.refresh_from_db()
    return user


@pytest.fixture
def article():
    content = AdhdContent.objects.create(
        title='Understanding Attention',
        description='Learn how attention works.',
        article_body={
            'version': 1,
            'blocks': [
                {'id': 'p-1', 'type': 'paragraph', 'data': {'text': 'Attention matters.'}},
            ],
        },
        is_management=True,
        age_group='adult',
        day=1,
        file_type='article',
        order_number=1,
        estimated_duration_minutes=8,
        status=ContentStatus.PUBLISHED,
    )
    question = ContentQuestion.objects.create(
        content=content,
        question_text='What matters?',
        question_type='single_choice',
        display_order=1,
        maximum_score=2,
    )
    QuestionOption.objects.create(question=question, option_text='Attention', is_correct=True, display_order=1)
    QuestionOption.objects.create(question=question, option_text='Distraction', is_correct=False, display_order=2)
    return content


@pytest.mark.django_db
class TestLearningContentApi:
    list_url = '/api/content/v1/contents?section=management'

    def test_content_list_requires_authentication(self, api_client):
        response = api_client.get(self.list_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_content_list_filters_user_age_and_unpublished_content(self, api_client, user, article):
        AdhdContent.objects.create(
            title='Draft Article',
            article_body={'blocks': [{'type': 'paragraph', 'data': {'text': 'Draft'}}]},
            is_management=True,
            age_group='adult',
            day=1,
            file_type='article',
            order_number=2,
            status=ContentStatus.DRAFT,
        )
        AdhdContent.objects.create(
            title='Child Article',
            article_body={'blocks': [{'type': 'paragraph', 'data': {'text': 'Child'}}]},
            is_management=True,
            age_group='child',
            day=1,
            file_type='article',
            order_number=1,
            status=ContentStatus.PUBLISHED,
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(self.list_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['pagination']['total_items'] == 1
        item = response.data['data']['results'][0]
        assert item['id'] == article.id
        assert item['content_type'] == 'article'
        assert item['has_questions'] is True
        assert item['question_count'] == 1
        assert item['is_locked'] is False
        assert 'article' not in item

    def test_day_two_is_locked_without_subscription(self, api_client, user):
        AdhdContent.objects.create(
            title='Day Two Article',
            article_body={'blocks': [{'type': 'paragraph', 'data': {'text': 'Day 2'}}]},
            is_management=True,
            age_group='adult',
            day=2,
            file_type='article',
            order_number=1,
            status=ContentStatus.PUBLISHED,
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(self.list_url)

        item = response.data['data']['results'][0]
        assert item['is_locked'] is True
        assert 'subscription' in item['locked_reason'].lower()

    def test_article_detail_returns_body(self, api_client, user, article):
        api_client.force_authenticate(user=user)
        response = api_client.get(f'/api/content/v1/contents/{article.id}')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['article']['version'] == 1
        assert response.data['data']['file_url'] is None
        assert response.data['data']['question_count'] == 1
        assert len(response.data['data']['questions']) == 1
        question = response.data['data']['questions'][0]
        assert question['question_text'] == 'What matters?'
        assert len(question['options']) == 2
        assert question['options'][0]['is_correct'] is True
        assert question['options'][1]['is_correct'] is False

    def test_content_detail_excludes_inactive_questions(self, api_client, user, article):
        ContentQuestion.objects.create(
            content=article,
            question_text='Hidden draft question',
            question_type='single_choice',
            display_order=2,
            is_active=False,
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(f'/api/content/v1/contents/{article.id}')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['question_count'] == 1
        assert [question['question_text'] for question in response.data['data']['questions']] == [
            'What matters?'
        ]

    def test_article_detail_returns_sanitized_ckeditor_html(self, api_client, user, article):
        article.article_content = (
            '<h1 style="font-size: 40px">Focus News</h1>'
            '<p><strong>Important</strong></p>'
            '<script>alert("unsafe")</script>'
        )
        article.save()
        article.refresh_from_db()
        api_client.force_authenticate(user=user)

        response = api_client.get(f'/api/content/v1/contents/{article.id}')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['article']['format'] == 'html'
        html = response.data['data']['article']['html']
        assert '<h1 style="font-size: 40px;">Focus News</h1>' in html
        assert '<strong>Important</strong>' in html
        assert '<script>' not in html

    def test_attempt_questions_hide_correct_answer(self, api_client, user, article):
        api_client.force_authenticate(user=user)
        start = api_client.post(f'/api/content/v1/contents/{article.id}/attempts', {}, format='json')
        attempt_id = start.data['data']['id']

        response = api_client.get(f'/api/content/v1/attempts/{attempt_id}/questions')

        assert response.status_code == status.HTTP_200_OK
        option = response.data['data']['questions'][0]['options'][0]
        assert 'is_correct' not in option

    def test_submit_scores_answers_and_updates_progress(self, api_client, user, article):
        api_client.force_authenticate(user=user)
        start = api_client.post(f'/api/content/v1/contents/{article.id}/attempts', {}, format='json')
        attempt_id = start.data['data']['id']
        question = article.questions.get()
        correct_option = question.options.get(is_correct=True)

        response = api_client.post(
            f'/api/content/v1/attempts/{attempt_id}/submit',
            {'answers': [{'question_id': question.id, 'selected_option_ids': [correct_option.id]}]},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['score'] == 2.0
        assert response.data['data']['maximum_score'] == 2.0
        assert response.data['data']['percentage'] == 100.0
        assert response.data['data']['passed'] is True
        assert response.data['data']['submitted'] is True
        assert ProgressTracker.objects.filter(user=user, day_number=1, file_type='article').exists()
        details = UserAssessmentDetails.objects.get(user=user)
        assert details.last_completed == 1
        assert details.is_day_completed is True

        repeat = api_client.post(
            f'/api/content/v1/attempts/{attempt_id}/submit',
            {'answers': [{'question_id': question.id, 'selected_option_ids': [correct_option.id]}]},
            format='json',
        )
        assert repeat.status_code == status.HTTP_200_OK
        assert repeat.data['data']['submitted'] is False
        assert ContentAttempt.objects.get(pk=attempt_id).answers.count() == 1

    def test_submit_rejects_missing_required_answer(self, api_client, user, article):
        api_client.force_authenticate(user=user)
        start = api_client.post(f'/api/content/v1/contents/{article.id}/attempts', {}, format='json')

        response = api_client.post(
            f"/api/content/v1/attempts/{start.data['data']['id']}/submit",
            {'answers': []},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'answers' in response.data['errors']

    def test_user_cannot_access_another_users_attempt(self, api_client, user, article):
        other_user = Users.objects.create_user(
            username='other_learning_user',
            email='other_learning_user@test.com',
            password='Password123!',
            dob='1990-01-01',
        )
        other_user.refresh_from_db()
        attempt = ContentAttempt.objects.create(user=other_user, content=article, attempt_number=1)
        api_client.force_authenticate(user=user)

        questions = api_client.get(f'/api/content/v1/attempts/{attempt.id}/questions')
        submit = api_client.post(f'/api/content/v1/attempts/{attempt.id}/submit', {'answers': []}, format='json')

        assert questions.status_code == status.HTTP_404_NOT_FOUND
        assert submit.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestContentAdminForm:
    def test_existing_article_only_renders_article_specific_section(self, user, article):
        user.is_staff = True
        user.is_superuser = True
        request = RequestFactory().get(f'/admin/filehandler/adhdcontent/{article.id}/change/')
        request.user = user
        model_admin = AdhdContentAdmin(AdhdContent, admin.site)

        fieldsets = model_admin.get_fieldsets(request, article)
        section_names = [name for name, _options in fieldsets]

        assert 'Article' in section_names
        assert 'Video or file' not in section_names
        assert 'Activity' not in section_names
        assert 'file_type' in model_admin.get_readonly_fields(request, article)

    def test_new_activity_only_renders_activity_specific_section(self, user):
        user.is_staff = True
        user.is_superuser = True
        request = RequestFactory().get('/admin/filehandler/adhdcontent/add/?type=activity')
        request.user = user
        model_admin = AdhdContentAdmin(AdhdContent, admin.site)

        fieldsets = model_admin.get_fieldsets(request)
        section_names = [name for name, _options in fieldsets]

        assert 'Activity' in section_names
        assert 'Article' not in section_names
        assert 'Video or file' not in section_names
