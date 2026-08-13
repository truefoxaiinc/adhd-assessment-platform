from django.contrib import admin
from django.contrib import messages
from django.utils import timezone

from apps.filehandler.learning_services import LearningContentService
from apps.filehandler.models import (
    AdhdContent,
    ContentAttempt,
    ContentQuestion,
    ContentStatus,
    FeedbackReview,
    QuestionOption,
)
from django.utils.html import format_html
from unfold.admin import ModelAdmin

@admin.register(AdhdContent)
class AdhdContentAdmin(ModelAdmin):
    list_display = ('title', 'content_phase', 'status', 'file_type', 'question_count', 'age_group', 'day', 'order_number', 'updated_at')
    list_filter = ('status', 'is_management', 'age_group', 'file_type', 'activity_name', 'day')
    search_fields = ('title', 'activity_name', 'file__name')
    ordering = ('is_management', 'age_group', 'day', 'order_number')
    date_hierarchy = 'created_at'
    list_per_page = 25
    actions = ('publish_content', 'archive_content')
    fieldsets = (
        ('Content', {'fields': ('title', 'description', 'file_type', 'status')}),
        ('Placement', {'fields': ('is_management', 'age_group', 'day', 'order_number')}),
        ('Article', {'fields': ('article_content', 'cover_image'), 'classes': ('article-fields',)}),
        ('Video or file', {'fields': ('file',), 'classes': ('file-fields',)}),
        ('Activity', {'fields': ('activity_name',), 'classes': ('activity-fields',)}),
        ('Learning', {'fields': ('estimated_duration_minutes', 'question_mode', 'published_at')}),
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault('status', ContentStatus.DRAFT)
        return initial

    class Media:
        js = ('filehandler/js/content_type_fields.js',)

    @admin.display(description='Phase', ordering='is_management')
    def content_phase(self, obj):
        if obj.is_management:
            return format_html('<span class="text-blue-700 font-semibold">Management</span>')
        return format_html('<span class="text-purple-700 font-semibold">Assessment</span>')

    @admin.display(description='Questions')
    def question_count(self, obj):
        return obj.questions.count()

    @admin.action(description='Publish selected content')
    def publish_content(self, request, queryset):
        published = 0
        for content in queryset.prefetch_related('questions__options'):
            try:
                content.full_clean()
                LearningContentService.validate_question_configuration(content)
            except Exception as exc:
                self.message_user(request, f'{content.title}: {exc}', level=messages.ERROR)
                continue
            content.status = ContentStatus.PUBLISHED
            content.published_at = timezone.now()
            content.save(update_fields=['status', 'published_at', 'updated_at'])
            published += 1
        if published:
            self.message_user(request, f'Published {published} content item(s).', level=messages.SUCCESS)

    @admin.action(description='Archive selected content')
    def archive_content(self, request, queryset):
        updated = queryset.update(status=ContentStatus.ARCHIVED)
        self.message_user(request, f'Archived {updated} content item(s).', level=messages.SUCCESS)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 2


@admin.register(ContentQuestion)
class ContentQuestionAdmin(ModelAdmin):
    list_display = ('question_preview', 'content', 'question_type', 'display_order', 'maximum_score', 'is_required', 'is_active')
    list_filter = ('question_type', 'is_required', 'is_active', 'content__is_management')
    search_fields = ('question_text', 'content__title')
    inlines = (QuestionOptionInline,)

    @admin.display(description='Question')
    def question_preview(self, obj):
        return obj.question_text[:80]


@admin.register(QuestionOption)
class QuestionOptionAdmin(ModelAdmin):
    list_display = ('option_text', 'question', 'display_order', 'is_correct')
    list_filter = ('is_correct', 'question__question_type')
    search_fields = ('option_text', 'question__question_text', 'question__content__title')


@admin.register(ContentAttempt)
class ContentAttemptAdmin(ModelAdmin):
    list_display = ('id', 'user', 'content', 'attempt_number', 'status', 'percentage', 'passed', 'started_at', 'completed_at')
    list_filter = ('status', 'passed', 'content__is_management', 'content__file_type')
    search_fields = ('user__email', 'user__username', 'content__title')
    readonly_fields = ('id', 'user', 'content', 'attempt_number', 'status', 'score', 'maximum_score', 'percentage', 'passed', 'started_at', 'completed_at')

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
