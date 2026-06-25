from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0005_userassessmentdetails_last_completed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='faceattentionsession',
            name='attention_engagement_rate',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='blink_ratio',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='brightness_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='eyes_closed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='face_detected',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='gaze_state',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='head_pose_ok',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='low_light',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='pitch',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='roll',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='video_attentive',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='yaw',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='yawn_distance',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='yawning',
            field=models.BooleanField(default=False),
        ),
    ]
