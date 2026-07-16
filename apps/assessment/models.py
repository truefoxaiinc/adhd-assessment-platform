from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from apps.users.models import Users
from helpers.abstract_models import AbstractDateFieldMix


class SelfAssessmentQuestions(AbstractDateFieldMix):
    class QUESTION_CATEGORY(models.TextChoices):
        RF    = 'RF', _('Reading Focus')
        VT    = 'VT', _('Visual Tracking')
        AL    = 'AL', _('Auditory/Listening')
        SR    = 'SR', _('Self Regulation')
        N     = 'N', _('Reverse Scored')


    question_text         = models.CharField(_('Question Text'), max_length = 300, blank = True, null = True)
    category              = models.CharField(_('Question Category'),choices=QUESTION_CATEGORY, max_length = 300, default=QUESTION_CATEGORY.N, blank = True, null = True)
    category_num          = models.CharField(_('Category Number'), max_length = 300, blank = True, null = True)
    is_for_adults         = models.BooleanField(default = False)
    is_active             = models.BooleanField(default = True)

    class Meta:
        verbose_name          = _("SelfAssessmentQuestions")
        verbose_name_plural   = _("SelfAssessmentQuestions")
        db_table              = 'SelfAssessmentQuestions'
        indexes = [
            models.Index(fields=['is_for_adults', 'is_active', '-id']),
        ]

    def __str__(self):
        return self.question_text or ''
       

class SelfAssessmentResult(models.Model):
    user                    = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="assesment_completed_by")
    result                  = models.CharField(_('Result'),max_length=300, blank = True, null = True)
    raw_total               = models.IntegerField(_('Raw Total Score'), default=0, null=True, blank=True)
    tenscore                = models.FloatField(_('Total Score In Ten'), default=0, null=True, blank=True)
    read_focus_total        = models.FloatField(_('RF Total Score'), default=0, null=True, blank=True)
    visual_tracking_total   = models.FloatField(_('VT Total Score'), default=0, null=True, blank=True)
    audio_listening_total   = models.FloatField(_('AL Total Score'), default=0, null=True, blank=True)
    program_duration        = models.IntegerField(_('Program Duration'), default=0, null=True, blank=True)
    created_at              = models.DateTimeField(_('Created At'), auto_now_add=True, null=True)
    completed_at            = models.DateTimeField(_('Completed At'), null=True, blank=True)

    def __str__(self):
        try:
            username = self.user.username or 'unknown user'
        except ObjectDoesNotExist:
            username = 'missing user'
        return f"Response by {username} for {self.result or 'pending result'}"

    class Meta:
        verbose_name          = _("SelfAssessmentResult")
        verbose_name_plural   = _("SelfAssessmentResult")
        db_table              = 'SelfAssessmentResult'
        indexes = [
            models.Index(fields=['user', '-id']),
            models.Index(fields=['user', '-completed_at'], name='assessment_user_completed_idx'),
        ]



class SelfAssessmentResponse(models.Model):

    class RESPONSE_CHOICES(models.TextChoices):
        NEVER       = '0', 'Never'
        RARELY      = '1', 'Rarely'
        SOMETIMES   = '2', 'Sometimes'
        OFTEN       = '3', 'Often'
        VERY_OFTEN  = '4', 'Very Often'

    result_entry    = models.ForeignKey(SelfAssessmentResult, on_delete=models.CASCADE, related_name="result_for_response",null=True, blank=True)
    question        = models.ForeignKey(SelfAssessmentQuestions, on_delete=models.CASCADE, related_name="assesment_question",null=True, blank=True)
    response        = models.CharField(_('Response'),max_length=300,choices=RESPONSE_CHOICES, default=RESPONSE_CHOICES.NEVER, blank = True, null = True)
    text_response   = models.TextField(_('Text Response'),null=True, blank=True)

    def __str__(self):
        try:
            username = self.result_entry.user.username or 'unknown user'
        except ObjectDoesNotExist:
            username = 'missing result'

        try:
            question_text = self.question.question_text or 'unknown question'
        except ObjectDoesNotExist:
            question_text = 'missing question'

        return f"Response by {username} for {question_text}"

    class Meta:
        verbose_name          = _("SelfAssessmentResponse")
        verbose_name_plural   = _("SelfAssessmentResponse")
        db_table              = 'SelfAssessmentResponse'
        indexes = [
            models.Index(fields=['result_entry', 'question']),
        ]



class ADHDDocument(models.Model):
    file = models.FileField(upload_to='adhd',null=True)
    name = models.CharField(_('Document Name'), max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name          = _("ADHDDocument")
        verbose_name_plural   = _("ADHDDocument")
        db_table              = 'ADHDDocument'
