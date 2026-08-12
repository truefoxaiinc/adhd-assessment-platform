from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.notifications.models import ProgramNotification, PushDevice


@admin.register(PushDevice)
class PushDeviceAdmin(ModelAdmin):
    list_display = ('id', 'user', 'platform', 'device_id', 'is_active', 'last_seen_at')
    list_filter = ('platform', 'is_active')
    search_fields = ('user__email', 'user__username', 'device_id')
    exclude = ('token',)
    readonly_fields = ('last_seen_at', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(ProgramNotification)
class ProgramNotificationAdmin(ModelAdmin):
    list_display = (
        'notification_id',
        'user',
        'newly_unlocked_day',
        'pending_activity_count',
        'is_sent',
        'sent_at',
    )
    list_filter = ('notification_type', 'is_sent', 'newly_unlocked_day')
    search_fields = ('notification_id', 'user__email', 'user__username')
    readonly_fields = (
        'user',
        'notification_id',
        'notification_type',
        'title',
        'body',
        'newly_unlocked_day',
        'pending_activity_count',
        'pending_days',
        'target_screen',
        'is_sent',
        'sent_at',
        'created_at',
    )

    def has_add_permission(self, request):
        return False
