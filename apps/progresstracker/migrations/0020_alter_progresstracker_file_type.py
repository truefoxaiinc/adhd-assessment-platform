from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0019_faceattentionsession_avg_sustained_duration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='progresstracker',
            name='file_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('article', 'Article'),
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
