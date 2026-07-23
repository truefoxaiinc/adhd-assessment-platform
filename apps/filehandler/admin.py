from django.contrib import admin
from apps.filehandler.models import AdhdContent, FeedbackReview
from django.utils.html import format_html
from unfold.admin import ModelAdmin

@admin.register(AdhdContent)
class AdhdContentAdmin(ModelAdmin):
    list_display = ('title', 'content_phase', 'file_type', 'activity_name', 'age_group', 'day', 'order_number', 'created_at')
    list_filter = ('is_management', 'age_group', 'file_type', 'activity_name', 'day')
    search_fields = ('title', 'activity_name', 'file__name')
    ordering = ('is_management', 'age_group', 'day', 'order_number')
    date_hierarchy = 'created_at'
    list_per_page = 25

    @admin.display(description='Phase', ordering='is_management')
    def content_phase(self, obj):
        if obj.is_management:
            return format_html('<span class="text-blue-700 font-semibold">Management</span>')
        return format_html('<span class="text-purple-700 font-semibold">Assessment</span>')

@admin.register(FeedbackReview)
class FeedbackReviewAdmin(ModelAdmin):
    list_display = ('user', 'feedback_preview', 'created_at')
    search_fields = ('user__username', 'user__email', 'feedback')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 25

    @admin.display(description='Feedback')
    def feedback_preview(self, obj):
        text = obj.feedback or ''
        return text[:90] + ('...' if len(text) > 90 else '')
