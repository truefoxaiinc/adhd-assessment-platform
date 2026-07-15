import pytest

from apps.users.models import Users
from apps.users.services.registration_service import RegistrationService


@pytest.mark.django_db
def test_registration_sets_initial_goal_flags():
    user = RegistrationService.create_user(
        username='flag_user',
        email='flag_user@test.com',
        password='Password123!',
    )

    assert user.is_first is True
    assert user.is_last is False


@pytest.mark.django_db
def test_user_manager_sets_initial_goal_flags_by_default():
    user = Users.objects.create_user(
        username='manager_flag_user',
        email='manager_flag_user@test.com',
        password='Password123!',
    )

    assert user.is_first is True
    assert user.is_last is False
