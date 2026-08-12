from celery import shared_task

from apps.notifications.models import PushDevice
from apps.notifications.services import create_pending_activity_notification
from apps.users.models import Users


@shared_task
def send_pending_activity_notifications():
    user_ids = PushDevice.objects.filter(is_active=True).values_list('user_id', flat=True).distinct()
    users = Users.objects.filter(
        id__in=user_ids,
        is_active=True,
        is_deleted=False,
    )
    checked = 0
    sent = 0
    for user in users.iterator():
        checked += 1
        notification, no_notification_data = create_pending_activity_notification(user)
        if notification and notification.is_sent and no_notification_data is None:
            sent += 1
    return {'checked': checked, 'sent': sent}
