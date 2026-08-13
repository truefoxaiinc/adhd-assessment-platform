import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.users.models import Users

class FeedbackReview(models.Model):
    user        = models.ForeignKey(Users, on_delete=models.CASCADE)
    feedback    = models.TextField(_('Feedback'), blank = True, null = True)
    created_at  = models.DateTimeField(_('Created AT'),auto_now_add=True, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        verbose_name          = _("FeedbackReview")
        verbose_name_plural   = _("FeedbackReview")
        db_table              = 'FeedbackReview'

class AgeGroupCategory(models.TextChoices):
    CHILD = 'child', _('Child')
    ADOLESCENTS = 'adolescents', _('Adolescents')
    ADULT = 'adult', _('Adult')

class FileTypeCategory(models.TextChoices):
    ARTICLE = 'article', _('Article')
    VIDEO = 'video', _('Video')
    DOCUMENT = 'document', _('Document')
    FILE = 'file', _('File')
    ACTIVITY = 'activity', _('Activity')


class ActivityNameCategory(models.TextChoices):
    MEMORY_FLIP = 'memory_flip', _('Memory Flip')
    TARGET_POP = 'target_pop', _('Target Pop')
    FOCUS_HUNT = 'focus_hunt', _('Focus Hunt')
    SEQUENCE_RECALL = 'sequence_recall', _('Sequence Recall')
    COLOUR_CONFLICT = 'colour_conflict', _('Colour Conflict')
    TASK_SWITCH = 'task_switch', _('Task Switch')


class ContentStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    PUBLISHED = 'published', _('Published')
    ARCHIVED = 'archived', _('Archived')


class QuestionMode(models.TextChoices):
    PRACTICE = 'practice', _('Practice')
    SCORED = 'scored', _('Scored')

class AdhdContent(models.Model):
    title            = models.CharField(_('Title'), max_length=255)
    description      = models.TextField(_('Description'), blank=True)
    file             = models.FileField(_('File'), upload_to='adhd_content/', blank=True, null=True)
    cover_image      = models.ImageField(_('Cover Image'), upload_to='adhd_content/covers/', blank=True, null=True)
    article_body     = models.JSONField(_('Article Body'), blank=True, null=True)
    is_management    = models.BooleanField(_('Is Management'), default=False, help_text="True for Management files, False for Assessment files")
    age_group        = models.CharField(_('Age Group'), max_length=50, choices=AgeGroupCategory.choices, default=AgeGroupCategory.ADULT)
    day              = models.IntegerField(_('Day'), blank=True, null=True, help_text="Required for management files. e.g. 1 for day-1")
    file_type        = models.CharField(_('File Type'), max_length=50, choices=FileTypeCategory.choices, default=FileTypeCategory.VIDEO)
    activity_name    = models.CharField(_('Activity Name'), max_length=50, choices=ActivityNameCategory.choices, blank=True, null=True)
    order_number     = models.IntegerField(_('Order Number'), default=1)
    estimated_duration_minutes = models.PositiveIntegerField(_('Estimated Duration Minutes'), default=0)
    question_mode    = models.CharField(_('Question Mode'), max_length=20, choices=QuestionMode.choices, default=QuestionMode.PRACTICE)
    status           = models.CharField(_('Status'), max_length=20, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED, db_index=True)
    published_at     = models.DateTimeField(_('Published At'), blank=True, null=True)
    created_at       = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at       = models.DateTimeField(_('Updated At'), auto_now=True)

    def clean(self):
        errors = {}
        if self.is_management and not self.day:
            errors['day'] = 'Day is required for management content.'
        if self.file_type == FileTypeCategory.ARTICLE:
            if not self.article_body:
                errors['article_body'] = 'Article body is required for article content.'
            elif not isinstance(self.article_body, dict) or not isinstance(self.article_body.get('blocks'), list):
                errors['article_body'] = 'Article body must be an object containing a blocks list.'
            else:
                allowed_blocks = {'heading', 'paragraph', 'bullet_list', 'numbered_list', 'image', 'callout', 'quote'}
                invalid_blocks = [
                    block.get('type')
                    for block in self.article_body['blocks']
                    if not isinstance(block, dict) or block.get('type') not in allowed_blocks
                ]
                if invalid_blocks:
                    errors['article_body'] = f'Unsupported article block types: {invalid_blocks}.'
        elif self.article_body:
            errors['article_body'] = 'Article body can only be used with article content.'
        if self.file_type == FileTypeCategory.ACTIVITY:
            if not self.activity_name:
                errors['activity_name'] = 'Activity name is required for activity content.'
        elif self.activity_name:
            errors['activity_name'] = 'Activity name can only be used with activity content.'
        if self.file_type not in (FileTypeCategory.ARTICLE, FileTypeCategory.ACTIVITY) and not self.file:
            errors['file'] = 'A file is required for video or legacy file content.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        phase = "Management" if self.is_management else "Assessment"
        day_str = f" Day {self.day}" if self.is_management and self.day else ""
        return f"[{phase}{day_str}] {self.title} ({self.age_group})"

    class Meta:
        verbose_name = _("ADHD Content")
        verbose_name_plural = _("ADHD Contents")
        db_table = 'AdhdContent'
        ordering = ['is_management', 'age_group', 'day', 'order_number']
        indexes = [
            models.Index(fields=['status', 'is_management', 'age_group', 'day'], name='content_list_idx'),
        ]


class QuestionType(models.TextChoices):
    SINGLE_CHOICE = 'single_choice', _('Single Choice')
    MULTIPLE_CHOICE = 'multiple_choice', _('Multiple Choice')
    TRUE_FALSE = 'true_false', _('True/False')


class ContentQuestion(models.Model):
    content = models.ForeignKey(AdhdContent, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=30, choices=QuestionType.choices, default=QuestionType.SINGLE_CHOICE)
    explanation = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=1)
    maximum_score = models.PositiveIntegerField(default=1)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.content.title}: {self.question_text[:60]}'

    class Meta:
        ordering = ['display_order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['content', 'display_order'], name='unique_question_order_per_content'),
        ]
        indexes = [models.Index(fields=['content', 'is_active', 'display_order'], name='content_question_list_idx')]


class QuestionOption(models.Model):
    question = models.ForeignKey(ContentQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.option_text

    class Meta:
        ordering = ['display_order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['question', 'display_order'], name='unique_option_order_per_question'),
        ]


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = 'in_progress', _('In Progress')
    COMPLETED = 'completed', _('Completed')
    ABANDONED = 'abandoned', _('Abandoned')


class ContentAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='content_attempts')
    content = models.ForeignKey(AdhdContent, on_delete=models.PROTECT, related_name='attempts')
    attempt_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=AttemptStatus.choices, default=AttemptStatus.IN_PROGRESS)
    score = models.FloatField(default=0.0)
    maximum_score = models.FloatField(default=0.0)
    percentage = models.FloatField(default=0.0)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'content', 'attempt_number'], name='unique_user_content_attempt'),
        ]
        indexes = [
            models.Index(fields=['user', 'content', 'status'], name='user_content_attempt_idx'),
        ]


class ContentAnswer(models.Model):
    attempt = models.ForeignKey(ContentAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(ContentQuestion, on_delete=models.PROTECT, related_name='answers')
    selected_options = models.ManyToManyField(QuestionOption, related_name='selected_answers', blank=True)
    is_correct = models.BooleanField(default=False)
    awarded_score = models.FloatField(default=0.0)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['attempt', 'question'], name='unique_answer_per_attempt_question'),
        ]
