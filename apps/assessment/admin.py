# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import SelfAssessmentQuestions, SelfAssessmentResult, SelfAssessmentResponse, ADHDDocument


@admin.register(SelfAssessmentQuestions)
class SelfAssessmentQuestionsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'created_by',
        'modified_by',
        'created_date',
        'modified_date',
        'status',
        'question_text',
        'category',
        'category_num',
        'is_for_adults',
        'is_active',
    )
    list_filter = (
        'created_date',
        'modified_date',
        'is_for_adults',
        'is_active',
    )


@admin.register(SelfAssessmentResult)
class SelfAssessmentResultAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'result',
        'raw_total',
        'tenscore',
        'read_focus_total',
        'visual_tracking_total',
        'audio_listening_total',
        'program_duration',
    )
    list_filter = ('user',)


@admin.register(SelfAssessmentResponse)
class SelfAssessmentResponseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'result_entry',
        'question',
        'response',
        'text_response',
    )
    list_filter = ('result_entry', 'question')


@admin.register(ADHDDocument)
class ADHDDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'name')
    search_fields = ('name',)
