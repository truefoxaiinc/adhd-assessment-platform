import logging
import json

from firebase_admin import messaging
from django.db import transaction
from django.utils import timezone

from apps.filehandler.models import AdhdContent
from apps.notifications.models import ProgramNotification, PushDevice
from apps.progresstracker.models import ManagementActivitySession, UserAssessmentDetails
from apps.progresstracker.services.track_services import ProgressTrackerActions
from project_adhd.firebase import initialize_firebase


logger = logging.getLogger(__name__)


def send_push_notification(
    device,
    title,
    body,
    data=None,
    channel_id='attention_minder_notifications',
    badge=None,
):
    initialize_firebase()
    message = messaging.Message(
        token=device.token,
        notification=messaging.Notification(title=title, body=body),
        data={str(key): str(value) for key, value in (data or {}).items()},
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                channel_id=channel_id,
                sound='default',
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound='default', badge=badge),
            ),
        ),
    )
    return messaging.send(message)


def notify_user(
    user,
    title,
    body,
    data=None,
    channel_id='attention_minder_notifications',
    badge=None,
):
    if not user or not user.is_active or user.is_deleted:
        return {'sent': 0, 'failed': 0}

    sent_count = 0
    failed_count = 0
    devices = PushDevice.objects.filter(user=user, is_active=True)

    for device in devices.iterator():
        try:
            send_push_notification(
                device,
                title,
                body,
                data,
                channel_id=channel_id,
                badge=badge,
            )
            sent_count += 1
        except (messaging.UnregisteredError, messaging.SenderIdMismatchError):
            PushDevice.objects.filter(pk=device.pk).update(is_active=False)
            failed_count += 1
            logger.info('Disabled invalid push device: device_id=%s user_id=%s', device.pk, user.pk)
        except Exception as exc:
            failed_count += 1
            logger.error(
                'Push delivery failed: device_id=%s user_id=%s error_type=%s',
                device.pk,
                user.pk,
                type(exc).__name__,
            )

    return {'sent': sent_count, 'failed': failed_count}


PENDING_ACTIVITY_NOTIFICATION_TYPE = 'previous_day_activities_pending'
PENDING_ACTIVITY_TARGET_SCREEN = 'attention_program_overview'


def _pending_activities(user, newly_unlocked_day):
    age_group = user.age_category or 'adult'
    activities = list(
        AdhdContent.objects.filter(
            is_management=True,
            age_group=age_group,
            file_type='activity',
            day__lt=newly_unlocked_day,
        ).values('id', 'day', 'activity_name')
    )
    if not activities:
        return []

    completed_sessions = ManagementActivitySession.objects.filter(
        user=user,
        status='completed',
        management_day__lt=newly_unlocked_day,
    )
    completed_content_ids = set(
        completed_sessions.exclude(content_id=None).values_list('content_id', flat=True)
    )
    completed_legacy_keys = set(
        completed_sessions.values_list('management_day', 'activity_code')
    )
    return [
        activity
        for activity in activities
        if activity['id'] not in completed_content_ids
        and (activity['day'], activity['activity_name']) not in completed_legacy_keys
    ]


def _no_notification_result(newly_unlocked_day, pending_activity_count=0):
    return {
        'notification_required': False,
        'newly_unlocked_day': newly_unlocked_day,
        'pending_activity_count': pending_activity_count,
    }


def create_pending_activity_notification(user):
    unlocked_days = ProgressTrackerActions.get_days_for_the_file(user) or [1]
    newly_unlocked_day = max(unlocked_days)
    progress = UserAssessmentDetails.objects.filter(user=user).first()
    expected_new_day = int(progress.last_completed or 0) + 1 if progress else 1
    if newly_unlocked_day <= 1 or newly_unlocked_day != expected_new_day:
        return None, _no_notification_result(newly_unlocked_day)

    pending_activities = _pending_activities(user, newly_unlocked_day)
    pending_activity_count = len(pending_activities)
    if not pending_activity_count:
        return None, _no_notification_result(newly_unlocked_day)

    pending_days = sorted({activity['day'] for activity in pending_activities})
    notification_id = f'day_{newly_unlocked_day}_pending_activities_user_{user.pk}'
    noun = 'activity' if pending_activity_count == 1 else 'activities'
    day_phrase = 'an earlier day' if pending_activity_count == 1 else 'earlier days'
    title = 'Complete your pending activities'
    body = (
        f'Day {newly_unlocked_day} is now available. You still have '
        f'{pending_activity_count} {noun} to complete from {day_phrase}.'
    )

    with transaction.atomic():
        notification, _ = ProgramNotification.objects.get_or_create(
            notification_id=notification_id,
            defaults={
                'user': user,
                'notification_type': PENDING_ACTIVITY_NOTIFICATION_TYPE,
                'title': title,
                'body': body,
                'newly_unlocked_day': newly_unlocked_day,
                'pending_activity_count': pending_activity_count,
                'pending_days': pending_days,
                'target_screen': PENDING_ACTIVITY_TARGET_SCREEN,
            },
        )
        notification = ProgramNotification.objects.select_for_update().get(pk=notification.pk)
        if notification.is_sent:
            return notification, _no_notification_result(
                newly_unlocked_day,
                pending_activity_count,
            )

        notification.title = title
        notification.body = body
        notification.pending_activity_count = pending_activity_count
        notification.pending_days = pending_days
        notification.save(update_fields=[
            'title',
            'body',
            'pending_activity_count',
            'pending_days',
        ])

        delivery = notify_user(
            user,
            title,
            body,
            {
                'notification_type': PENDING_ACTIVITY_NOTIFICATION_TYPE,
                'notification_id': notification_id,
                'newly_unlocked_day': str(newly_unlocked_day),
                'pending_activity_count': str(pending_activity_count),
                'pending_days': json.dumps(pending_days, separators=(',', ':')),
                'target_screen': PENDING_ACTIVITY_TARGET_SCREEN,
                'is_management': 'true',
            },
            channel_id='program_reminders',
            badge=1,
        )
        if delivery['sent'] > 0:
            notification.is_sent = True
            notification.sent_at = timezone.now()
            notification.save(update_fields=['is_sent', 'sent_at'])

    return notification, None


def serialize_program_notification(notification):
    return {
        'notification_id': notification.notification_id,
        'notification_type': notification.notification_type,
        'title': notification.title,
        'body': notification.body,
        'newly_unlocked_day': notification.newly_unlocked_day,
        'pending_activity_count': notification.pending_activity_count,
        'pending_days': notification.pending_days,
        'target_screen': notification.target_screen,
        'is_sent': notification.is_sent,
        'sent_at': notification.sent_at,
    }
