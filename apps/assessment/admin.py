# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from .models import SelfAssessmentQuestions, SelfAssessmentResult, SelfAssessmentResponse, ADHDDocument


from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm

@admin.register(SelfAssessmentQuestions)
class SelfAssessmentQuestionsAdmin(ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm

    list_display = (
        'id',
        'question_preview',
        'category_badge',
        'question_text',
        'category_num',
        'audience_badge',
        'active_badge',
        'created_date',
    )
    list_filter = (
        'created_date',
        'modified_date',
        'is_for_adults',
        'is_active',
    )
    search_fields = ('question_text', 'category_num')
    ordering = ('-id',)
    list_per_page = 25

    @admin.display(description='Question')
    def question_preview(self, obj):
        text = obj.question_text or ''
        return text[:70] + ('...' if len(text) > 70 else '')

    @admin.display(description='Category', ordering='category')
    def category_badge(self, obj):
        return format_html('<span class="font-semibold text-primary-700">{}</span>', obj.get_category_display())

    @admin.display(description='Audience', ordering='is_for_adults')
    def audience_badge(self, obj):
        return 'Adults' if obj.is_for_adults else 'Children'

    @admin.display(description='Active', boolean=True, ordering='is_active')
    def active_badge(self, obj):
        return obj.is_active


@admin.register(SelfAssessmentResult)
class SelfAssessmentResultAdmin(ModelAdmin):
    list_display = (
        'id',
        'user',
        'result',
        'raw_total',
        'tenscore',
        'score_status',
        'read_focus_total',
        'visual_tracking_total',
        'audio_listening_total',
        'program_duration',
    )
    list_filter = ('user',)
    search_fields = ('user__email', 'user__username', 'result')
    ordering = ('-id',)
    list_per_page = 25

    @admin.display(description='Score band', ordering='tenscore')
    def score_status(self, obj):
        score = obj.tenscore or 0
        if score >= 7:
            return format_html('<span class="text-red-700 font-semibold">High</span>')
        if score >= 4:
            return format_html('<span class="text-amber-700 font-semibold">Moderate</span>')
        return format_html('<span class="text-green-700 font-semibold">Low</span>')


@admin.register(SelfAssessmentResponse)
class SelfAssessmentResponseAdmin(ModelAdmin):
    list_display = (
        'id',
        'result_entry',
        'question',
        'response',
        'text_response',
    )
    list_filter = ('result_entry', 'question')
    search_fields = ('result_entry__user__email', 'question__question_text', 'text_response')
    list_per_page = 25


@admin.register(ADHDDocument)
class ADHDDocumentAdmin(ModelAdmin):
    list_display = ('id', 'name', 'file')
    search_fields = ('name',)
    list_per_page = 25
