from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.filehandler.models import AdhdContent
from apps.users.models import Users


class FaceAttentionSession(models.Model):
    user                  = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='attention_sessions')
    file                  = models.ForeignKey(AdhdContent, on_delete=models.SET_NULL, related_name='attention_sessions', blank=True, null=True)
    session_id            = models.CharField(max_length=100)
    is_assessment         = models.BooleanField(default=False)
    concentration_score   = models.FloatField()
    gaze_ratio_avg        = models.FloatField(default=0.0)
    inattention_duration  = models.FloatField(default=0.0)
    drowsy_state          = models.FloatField(default=0.0)
    brightness_score      = models.FloatField(default=0.0)
    pitch                 = models.FloatField(default=0.0)
    yaw                   = models.FloatField(default=0.0)
    roll                  = models.FloatField(default=0.0)
    blink_ratio           = models.FloatField(default=0.0)
    yawn_distance         = models.FloatField(default=0.0)
    attention_engagement_rate = models.FloatField(default=0.0)
    total_processed_frames = models.IntegerField(default=0)
    sampled_frames = models.IntegerField(default=0)
    average_confidence = models.FloatField(default=0.0)
    average_concentration_score = models.FloatField(default=0.0)
    bad_frame_count = models.IntegerField(default=0)
    blurry_frame_count = models.IntegerField(default=0)
    low_light_frame_count = models.IntegerField(default=0)
    eyes_closed_count = models.IntegerField(default=0)
    gaze_warning_count = models.IntegerField(default=0)
    session_duration_seconds = models.FloatField(default=0.0)
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['user', '-created_at'],
                name='face_session_user_created_idx',
            ),
            models.Index(
                fields=['user', '-average_concentration_score'],
                name='face_session_user_score_idx',
            ),
            models.Index(
                fields=['user', 'is_assessment', '-created_at'],
                name='face_user_assessment_idx',
            ),
        ]

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
