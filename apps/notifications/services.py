import logging

from firebase_admin import messaging

from apps.notifications.models import PushDevice
from project_adhd.firebase import initialize_firebase


logger = logging.getLogger(__name__)


def send_push_notification(device, title, body, data=None):
    initialize_firebase()
    message = messaging.Message(
        token=device.token,
        notification=messaging.Notification(title=title, body=body),
        data={str(key): str(value) for key, value in (data or {}).items()},
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                channel_id='attention_minder_notifications',
                sound='default',
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound='default'),
            ),
        ),
    )
    return messaging.send(message)


def notify_user(user, title, body, data=None):
    if not user or not user.is_active or user.is_deleted:
        return {'sent': 0, 'failed': 0}

    sent_count = 0
    failed_count = 0
    devices = PushDevice.objects.filter(user=user, is_active=True)

    for device in devices.iterator():
        try:
            send_push_notification(device, title, body, data)
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
