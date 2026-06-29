from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0006_faceattentionsession_attention_metrics'),
    ]

    operations = [
        migrations.AddField(
            model_name='faceattentionsession',
            name='average_concentration_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='average_confidence',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='bad_frame_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='blurry_frame_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='eyes_closed_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='gaze_warning_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='low_light_frame_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='sampled_frames',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='session_duration_seconds',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='faceattentionsession',
            name='total_processed_frames',
            field=models.IntegerField(default=0),
        ),
    ]
