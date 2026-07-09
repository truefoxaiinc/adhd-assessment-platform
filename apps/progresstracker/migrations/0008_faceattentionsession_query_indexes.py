from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0007_faceattentionsession_aggregate_metrics'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='faceattentionsession',
            index=models.Index(
                fields=['user', '-created_at'],
                name='face_session_user_created_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='faceattentionsession',
            index=models.Index(
                fields=['user', '-average_concentration_score'],
                name='face_session_user_score_idx',
            ),
        ),
    ]
