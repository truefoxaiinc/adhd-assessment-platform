from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0015_simplify_usergoal'),
    ]

    operations = [
        migrations.AddField(
            model_name='faceattentionsession',
            name='calculation_version',
            field=models.CharField(default='frontend_attention_v1', max_length=100),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='content_type',
            field=models.CharField(default='video', max_length=50),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='final_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='gaze_quality_avg',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='idle_distracted_frames',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='maximum_inattention_duration',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='reading_engagement_rate',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='reading_focused_frames',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='reading_gaze_amplitude_avg',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='reading_gaze_frequency_avg_hz',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='watching_video_frames',
            field=models.IntegerField(default=0),
        ),
    ]
