from django.contrib import admin
from apps.filehandler.models import AdhdContent, FeedbackReview

@admin.register(AdhdContent)
class AdhdContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'file_type', 'is_management', 'age_group', 'day', 'order_number', 'created_at')
    list_filter = ('is_management', 'age_group', 'file_type', 'day')
    search_fields = ('title', 'file__name')
    ordering = ('is_management', 'age_group', 'day', 'order_number')

@admin.register(FeedbackReview)
class FeedbackReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__username', 'user__email')
