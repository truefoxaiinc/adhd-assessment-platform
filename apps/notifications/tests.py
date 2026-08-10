from unittest.mock import patch

import pytest
from firebase_admin import messaging
from rest_framework import status
from rest_framework.test import APIClient

from apps.notifications.models import PushDevice
from apps.notifications.services import notify_user
from apps.users.models import Users


REGISTER_URL = '/api/notifications/v1/devices/register/'
UNREGISTER_URL = '/api/notifications/v1/devices/unregister/'


@pytest.fixture
def user():
    return Users.objects.create_user(
        username='push_user',
        email='push_user@test.com',
        password='Password123!',
        is_verified=True,
    )


@pytest.fixture
def authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_device_registration_requires_authentication(client):
    response = client.post(
        REGISTER_URL,
        {'token': 'fcm-token', 'platform': 'android'},
        content_type='application/json',
    )
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
def test_registers_device_for_authenticated_user_without_returning_token(authed_client, user):
    response = authed_client.post(
        REGISTER_URL,
        {'token': 'private-fcm-token', 'platform': 'android', 'device_id': 'installation-1'},
        format='json',
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert 'token' not in response.data['data']
    assert PushDevice.objects.filter(user=user, token='private-fcm-token', is_active=True).exists()


@pytest.mark.django_db
def test_token_refresh_deactivates_previous_token_for_installation(authed_client, user):
    PushDevice.objects.create(
        user=user,
        token='old-fcm-token',
        platform='android',
        device_id='installation-1',
    )

    response = authed_client.post(
        REGISTER_URL,
        {'token': 'new-fcm-token', 'platform': 'android', 'device_id': 'installation-1'},
        format='json',
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert PushDevice.objects.get(token='old-fcm-token').is_active is False
    assert PushDevice.objects.get(token='new-fcm-token').is_active is True


@pytest.mark.django_db
def test_unregister_only_deactivates_authenticated_users_device(authed_client, user):
    other = Users.objects.create_user(username='other_push', email='other_push@test.com')
    PushDevice.objects.create(user=other, token='other-token', platform='ios')

    response = authed_client.delete(
        UNREGISTER_URL,
        {'token': 'other-token'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert PushDevice.objects.get(token='other-token').is_active is True


@pytest.mark.django_db
def test_notify_user_disables_unregistered_token(user):
    device = PushDevice.objects.create(user=user, token='invalid-token', platform='android')

    with patch(
        'apps.notifications.services.send_push_notification',
        side_effect=messaging.UnregisteredError('Token is not registered'),
    ):
        result = notify_user(user, 'Title', 'Body', {'type': 'lesson_ready'})

    device.refresh_from_db()
    assert device.is_active is False
    assert result == {'sent': 0, 'failed': 1}
