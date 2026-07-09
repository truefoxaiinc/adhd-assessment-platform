from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0009_faceattentionsession_is_assessment'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='faceattentionsession',
            index=models.Index(
                fields=['user', 'is_assessment', '-created_at'],
                name='face_user_assessment_idx',
            ),
        ),
    ]
