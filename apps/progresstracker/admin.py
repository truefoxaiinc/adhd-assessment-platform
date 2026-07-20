# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import UserAssessmentDetails, ProgressTracker, FaceAttentionSession, UserGoal


@admin.register(UserAssessmentDetails)
class UserAssessmentDetailsAdmin(ModelAdmin):
    list_display = (
        'id',
        'user',
        'course_duration',
        'last_completed',
        'completion_status',
        'started_on',
    )
    list_filter = ('user', 'started_on')
    search_fields = ('user__email', 'user__username')
    date_hierarchy = 'started_on'
    list_per_page = 25

    @admin.display(description='Status')
    def completion_status(self, obj):
        if obj.is_day_completed:
            return format_html('<span class="text-green-700 font-semibold">Completed</span>')
        return format_html('<span class="text-amber-700 font-semibold">In progress</span>')


@admin.register(ProgressTracker)
class ProgressTrackerAdmin(ModelAdmin):
    list_display = ('id', 'user', 'day_number', 'file_type', 'order_number', 'completion_badge')
    list_filter = ('user', 'file_type', 'is_day_completed')
    search_fields = ('user__email', 'user__username', 'order_number')
    ordering = ('user', 'day_number', 'order_number')
    list_per_page = 25

    @admin.display(description='Completion', boolean=True, ordering='is_day_completed')
    def completion_badge(self, obj):
        return obj.is_day_completed

@admin.register(FaceAttentionSession)
class FaceAttentionSessionAdmin(ModelAdmin):
    list_display = (
        'id',
        'user',
        'file',
        'session_id',
        'content_type',
        'final_score',
        'concentration_score',
        'attention_engagement_rate',
        'reading_engagement_rate',
        'focus_status',
        'gaze_ratio_avg',
        'inattention_duration',
        'drowsy_state',
        'created_at',
    )
    list_filter = ('user', 'file', 'content_type', 'is_assessment', 'created_at')
    search_fields = ('user__email', 'user__username', 'session_id', 'file__title')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 25

    @admin.display(description='Focus band', ordering='concentration_score')
    def focus_status(self, obj):
        score = obj.concentration_score
        if score >= 70:
            return format_html('<span class="text-green-700 font-semibold">Strong</span>')
        if score >= 50:
            return format_html('<span class="text-amber-700 font-semibold">Watch</span>')
        return format_html('<span class="text-red-700 font-semibold">Low</span>')


@admin.register(UserGoal)
class UserGoalAdmin(ModelAdmin):
    list_display = ('id', 'user', 'short_goal', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__email', 'user__username', 'goal')
    ordering = ('user', 'created_at', 'id')
    list_per_page = 25

    @admin.display(description='Goal')
    def short_goal(self, obj):
        if len(obj.goal) <= 60:
            return obj.goal
        return f'{obj.goal[:57]}...'
