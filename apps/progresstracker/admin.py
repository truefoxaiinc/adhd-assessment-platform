# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import UserAssessmentDetails, ProgressTracker, FaceAttentionSession


@admin.register(UserAssessmentDetails)
class UserAssessmentDetailsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'course_duration',
        'last_completed',
        'started_on',
    )
    list_filter = ('user', 'started_on')


@admin.register(ProgressTracker)
class ProgressTrackerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'day_number', 'file_type', 'order_number', 'is_day_completed')
    list_filter = ('user', 'is_day_completed')

@admin.register(FaceAttentionSession)
class FaceAttentionSessionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'session_id',
        'concentration_score',
        'gaze_ratio_avg',
        'inattention_duration',
        'drowsy_state',
        'created_at',
    )
    list_filter = ('user', 'created_at')
