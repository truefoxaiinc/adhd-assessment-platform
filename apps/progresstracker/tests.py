import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.progresstracker.models import UserGoal
from apps.users.models import Users


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

    def test_user_can_add_multiple_goals_with_ratings(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.GOALS_URL,
            {
                'goals': [
                    {'goal': 'Improve focus', 'rating': 4},
                    {'goal': 'Complete course', 'rating': 5},
                ],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['is_first'] is False
        assert response.data['is_last'] is False
        assert len(response.data['data']) == 2
        assert response.data['data'][0]['goal'] == 'Improve focus'
        assert response.data['data'][0]['rating'] == 4
        assert UserGoal.objects.filter(user=user).count() == 2
        user.refresh_from_db()
        assert user.is_first is False

    def test_user_can_fetch_own_goals(self, api_client, user):
        UserGoal.objects.create(user=user, goal='Improve focus', rating=4)
        api_client.force_authenticate(user=user)

        response = api_client.get(self.GOALS_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data'][0]['goal'] == 'Improve focus'
        assert response.data['data'][0]['rating'] == 4

    def test_user_can_update_own_goal_rating(self, api_client, user):
        goal = UserGoal.objects.create(user=user, goal='Improve focus', rating=2)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f'{self.GOALS_URL}/{goal.id}',
            {'rating': 5},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        goal.refresh_from_db()
        assert goal.rating == 5

    def test_user_can_mark_last_using_goal_api(self, api_client, user):
        goal = UserGoal.objects.create(user=user, goal='Complete course', rating=4)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f'{self.GOALS_URL}/{goal.id}',
            {'is_last': True},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_first'] is False
        assert response.data['is_last'] is True
        user.refresh_from_db()
        assert user.is_first is False
        assert user.is_last is True

    def test_user_cannot_update_another_users_goal(self, api_client, user):
        other_user = Users.objects.create_user(
            username='other_goal_user',
            email='other_goal_user@test.com',
            password='Password123!',
        )
        other_goal = UserGoal.objects.create(user=other_user, goal='Private goal', rating=1)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f'{self.GOALS_URL}/{other_goal.id}',
            {'rating': 5},
            format='json',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        other_goal.refresh_from_db()
        assert other_goal.rating == 1
