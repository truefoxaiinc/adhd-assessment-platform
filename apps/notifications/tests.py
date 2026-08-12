from unittest.mock import patch

import pytest
from django.utils import timezone
from firebase_admin import messaging
from rest_framework import status
from rest_framework.test import APIClient

from apps.filehandler.models import AdhdContent
from apps.notifications.models import ProgramNotification, PushDevice
from apps.notifications.services import create_pending_activity_notification, notify_user
from apps.progresstracker.models import ManagementActivitySession, UserAssessmentDetails
from apps.users.models import Users


REGISTER_URL = '/api/notifications/v1/devices/register/'
UNREGISTER_URL = '/api/notifications/v1/devices/unregister/'
PENDING_ACTIVITY_URL = '/api/notifications/v1/pending-activities/check/'


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


@pytest.mark.django_db
def test_pending_activity_notification_matches_contract_and_is_sent_once(user):
    UserAssessmentDetails.objects.create(user=user, last_completed=4)
    completed_activity = AdhdContent.objects.create(
        title='Day 2 Focus Hunt',
        is_management=True,
        age_group='adult',
        day=2,
        file_type='activity',
        activity_name='focus_hunt',
        order_number=1,
    )
    ManagementActivitySession.objects.create(
        user=user,
        content=completed_activity,
        activity_code='focus_hunt',
        management_day=2,
        status='completed',
        started_at=timezone.now(),
    )
    AdhdContent.objects.create(
        title='Day 3 Memory Flip',
        is_management=True,
        age_group='adult',
        day=3,
        file_type='activity',
        activity_name='memory_flip',
        order_number=1,
    )
    AdhdContent.objects.create(
        title='Day 4 Target Pop',
        is_management=True,
        age_group='adult',
        day=4,
        file_type='activity',
        activity_name='target_pop',
        order_number=1,
    )

    with patch(
        'apps.notifications.services.ProgressTrackerActions.get_days_for_the_file',
        return_value=[1, 2, 3, 4, 5],
    ), patch(
        'apps.notifications.services.notify_user',
        return_value={'sent': 1, 'failed': 0},
    ) as send:
        notification, no_notification_data = create_pending_activity_notification(user)
        duplicate, duplicate_data = create_pending_activity_notification(user)

    assert no_notification_data is None
    assert notification.notification_id == f'day_5_pending_activities_user_{user.pk}'
    assert notification.notification_type == 'previous_day_activities_pending'
    assert notification.title == 'Complete your pending activities'
    assert notification.body == (
        'Day 5 is now available. You still have 2 activities to complete from earlier days.'
    )
    assert notification.pending_activity_count == 2
    assert notification.pending_days == [3, 4]
    assert notification.target_screen == 'attention_program_overview'
    assert notification.is_sent is True
    assert notification.sent_at is not None
    assert duplicate.pk == notification.pk
    assert duplicate_data['notification_required'] is False
    assert ProgramNotification.objects.count() == 1
    send.assert_called_once()
    _, _, _, data = send.call_args.args
    assert data == {
        'notification_type': 'previous_day_activities_pending',
        'notification_id': f'day_5_pending_activities_user_{user.pk}',
        'newly_unlocked_day': '5',
        'pending_activity_count': '2',
        'pending_days': '[3,4]',
        'target_screen': 'attention_program_overview',
        'is_management': 'true',
    }
    assert send.call_args.kwargs == {'channel_id': 'program_reminders', 'badge': 1}


@pytest.mark.django_db
def test_pending_activity_api_returns_no_notification_when_all_activities_complete(
    authed_client,
    user,
):
    UserAssessmentDetails.objects.create(user=user, last_completed=1)

    with patch(
        'apps.notifications.services.ProgressTrackerActions.get_days_for_the_file',
        return_value=[1, 2],
    ):
        response = authed_client.post(PENDING_ACTIVITY_URL, {}, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data['message'] == 'No pending activity notification required.'
    assert response.data['data'] == {
        'notification_required': False,
        'newly_unlocked_day': 2,
        'pending_activity_count': 0,
    }
