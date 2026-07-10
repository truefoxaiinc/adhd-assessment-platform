from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0011_faceattentionsession_file_remove_detection_flags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='faceattentionsession',
            name='gaze_ratio_avg',
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name='faceattentionsession',
            name='drowsy_state',
            field=models.FloatField(default=0.0),
        ),
    ]
