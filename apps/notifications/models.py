from django.conf import settings
from django.db import models


class PushPlatform(models.TextChoices):
    ANDROID = 'android', 'Android'
    IOS = 'ios', 'iOS'


class PushDevice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_devices',
    )
    token = models.TextField(unique=True)
    platform = models.CharField(max_length=10, choices=PushPlatform.choices)
    device_id = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'PushDevice'
        indexes = [
            models.Index(fields=['user', 'is_active'], name='push_device_user_active_idx'),
            models.Index(fields=['device_id'], name='push_device_device_id_idx'),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.platform}:{self.pk}'


class ProgramNotification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='program_notifications',
    )
    notification_id = models.CharField(max_length=255, unique=True)
    notification_type = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    body = models.TextField()
    newly_unlocked_day = models.PositiveIntegerField()
    pending_activity_count = models.PositiveIntegerField(default=0)
    pending_days = models.JSONField(default=list)
    target_screen = models.CharField(max_length=100)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ProgramNotification'
        indexes = [
            models.Index(
                fields=['user', 'notification_type', 'newly_unlocked_day'],
                name='program_notice_user_day_idx',
            ),
        ]

    def __str__(self):
        return self.notification_id
