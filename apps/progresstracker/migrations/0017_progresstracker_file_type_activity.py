from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0016_faceattentionsession_reading_telemetry'),
    ]

    operations = [
        migrations.AlterField(
            model_name='progresstracker',
            name='file_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('video', 'Video'),
                    ('file', 'File'),
                    ('document', 'Document'),
                    ('activity', 'Activity'),
                ],
                max_length=50,
                null=True,
                verbose_name='File Type',
            ),
        ),
    ]
