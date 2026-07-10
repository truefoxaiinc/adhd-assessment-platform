from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('filehandler', '0002_adhdcontent'),
        ('progresstracker', '0010_faceattentionsession_assessment_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='faceattentionsession',
            name='file',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attention_sessions',
                to='filehandler.adhdcontent',
            ),
        ),
        migrations.RemoveField(
            model_name='faceattentionsession',
            name='face_detected',
        ),
        migrations.RemoveField(
            model_name='faceattentionsession',
            name='video_attentive',
        ),
        migrations.RemoveField(
            model_name='faceattentionsession',
            name='eyes_closed',
        ),
        migrations.RemoveField(
            model_name='faceattentionsession',
            name='yawning',
        ),
        migrations.RemoveField(
            model_name='faceattentionsession',
            name='gaze_state',
        ),
        migrations.RemoveField(
            model_name='faceattentionsession',
            name='head_pose_ok',
        ),
        migrations.RemoveField(
            model_name='faceattentionsession',
            name='low_light',
        ),
    ]
