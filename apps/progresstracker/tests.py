import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta

from apps.progresstracker.models import UserGoal
from apps.users.models import Users
from apps.users.services.registration_service import RegistrationService


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return Users.objects.create_user(
        username='goal_user',
        email='goal_user@test.com',
        password='Password123!',
    )


@pytest.mark.django_db
class TestUserGoals:
    GOALS_URL = '/api/progresstracker/v1/progress-track/goals'

    def test_registration_creates_initial_goal(self):
        user = RegistrationService.create_user(
            username='new_goal_user',
            email='new_goal_user@test.com',
            password='Password123!',
        )

        goal = UserGoal.objects.get(user=user)
        assert goal.is_first is True
        assert goal.is_last is False
        assert goal.goal == ''
        assert goal.rating == 0

    def test_user_can_add_multiple_goals(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.GOALS_URL,
            {
                'goals': ['Improve focus', 'Finish course'],
                'rating': 4,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_first'] is False
        assert response.data['is_last'] is False
        assert response.data['rating'] == 4
        assert len(response.data['data']) == 2
        assert set(response.data['data'][0].keys()) == {
            'id',
            'goal',
            'created_at',
            'updated_at',
        }
        assert UserGoal.objects.filter(user=user, is_first=False).count() == 2

    def test_first_goal_becomes_false_after_registration_day(self, api_client, user):
        first_goal = UserGoal.objects.create(user=user, is_first=True)
        UserGoal.objects.filter(pk=first_goal.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(self.GOALS_URL)

        assert response.status_code == status.HTTP_200_OK
        first_goal.refresh_from_db()
        assert first_goal.is_first is False
        assert response.data['is_first'] is False

    def test_user_can_update_own_goal_rating_and_last_flag(self, api_client, user):
        goal = UserGoal.objects.create(user=user, goal='Finish course')
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f'{self.GOALS_URL}/{goal.id}',
            {
                'goal': 'Finish full course',
                'rating': 5,
                'is_last': True,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        goal.refresh_from_db()
        assert goal.goal == 'Finish full course'
        assert goal.rating == 5
        assert goal.is_last is True
        assert response.data['is_last'] is True
        assert response.data['rating'] == 5
        assert response.data['data'][0]['goal'] == 'Finish full course'
        assert 'rating' not in response.data['data'][0]
        assert 'is_last' not in response.data['data'][0]

    def test_user_cannot_update_another_users_goal(self, api_client, user):
        other_user = Users.objects.create_user(
            username='other_goal_user',
            email='other_goal_user@test.com',
            password='Password123!',
        )
        other_goal = UserGoal.objects.create(user=other_user, goal='Private goal')
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f'{self.GOALS_URL}/{other_goal.id}',
            {'rating': 5},
            format='json',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        other_goal.refresh_from_db()
        assert other_goal.rating == 0
