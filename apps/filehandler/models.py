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

class AdhdContent(models.Model):
    title            = models.CharField(_('Title'), max_length=255)
    file             = models.FileField(_('File'), upload_to='adhd_content/', blank=True, null=True)
    is_management    = models.BooleanField(_('Is Management'), default=False, help_text="True for Management files, False for Assessment files")
    age_group        = models.CharField(_('Age Group'), max_length=50, choices=AgeGroupCategory.choices, default=AgeGroupCategory.ADULT)
    day              = models.IntegerField(_('Day'), blank=True, null=True, help_text="Required for management files. e.g. 1 for day-1")
    file_type        = models.CharField(_('File Type'), max_length=50, choices=FileTypeCategory.choices, default=FileTypeCategory.VIDEO)
    activity_name    = models.CharField(_('Activity Name'), max_length=50, choices=ActivityNameCategory.choices, blank=True, null=True)
    order_number     = models.IntegerField(_('Order Number'), default=1)
    created_at       = models.DateTimeField(_('Created At'), auto_now_add=True)

    def __str__(self):
        phase = "Management" if self.is_management else "Assessment"
        day_str = f" Day {self.day}" if self.is_management and self.day else ""
        return f"[{phase}{day_str}] {self.title} ({self.age_group})"

    class Meta:
        verbose_name = _("ADHD Content")
        verbose_name_plural = _("ADHD Contents")
        db_table = 'AdhdContent'
        ordering = ['is_management', 'age_group', 'day', 'order_number']
