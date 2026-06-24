from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.users.models import Users


class FaceAttentionSession(models.Model):
    user                  = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='attention_sessions')
    session_id            = models.CharField(max_length=100)
    concentration_score   = models.FloatField()
    gaze_ratio_avg        = models.FloatField(default=1.0)
    inattention_duration  = models.FloatField(default=0.0)
    drowsy_state          = models.FloatField(default=0.2)
    created_at            = models.DateTimeField(auto_now_add=True)

class UserAssessmentDetails(models.Model):
    user              = models.ForeignKey(Users, on_delete=models.CASCADE)
    course_duration   = models.IntegerField(_('Course Duration Days'),blank = True, null = True)
    last_completed    = models.IntegerField(_('Last Completed Day'),blank = True, null = True)
    last_completed_at = models.DateTimeField(_('Last Completed At'), blank=True, null=True)
    started_on        = models.DateTimeField(_('Course Started On'),auto_now_add=True, blank=True, null=True)
    is_day_completed  = models.BooleanField(_('Is Day Completed'), default=False)

    def __str__(self):
        return f"{self.user.username}"
    
    class Meta:
        verbose_name          = _("UserAssessmentDetails")
        verbose_name_plural   = _("UserAssessmentDetails")
        db_table              = 'UserAssessmentDetails'

class FILE_TYPE_CHOICES(models.TextChoices):
    VIDEO    = 'video', _('Video')
    FILE     = 'file', _('File')

class ProgressTracker(models.Model):
    user                = models.ForeignKey(Users, on_delete=models.CASCADE)
    day_number          = models.IntegerField(_('Day Number'),blank = True, null = True)
    file_type           = models.CharField(_('File Type'),choices=FILE_TYPE_CHOICES.choices, max_length=50, blank = True, null = True)
    order_number        = models.CharField(_('Order Number'), max_length=50, blank = True, null = True)
    is_day_completed    = models.BooleanField(_('Is Day Completed'), default=False)

    class Meta:
        verbose_name          = _("ProgressTracker")
        verbose_name_plural   = _("ProgressTracker")
        db_table              = 'ProgressTracker'
