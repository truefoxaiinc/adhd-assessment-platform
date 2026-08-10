from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.notifications.models import PushDevice


@admin.register(PushDevice)
class PushDeviceAdmin(ModelAdmin):
    list_display = ('id', 'user', 'platform', 'device_id', 'is_active', 'last_seen_at')
    list_filter = ('platform', 'is_active')
    search_fields = ('user__email', 'user__username', 'device_id')
    exclude = ('token',)
    readonly_fields = ('last_seen_at', 'created_at')

    def has_add_permission(self, request):
        return False
