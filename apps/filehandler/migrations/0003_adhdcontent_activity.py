from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filehandler', '0002_adhdcontent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adhdcontent',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='adhd_content/', verbose_name='File'),
        ),
        migrations.AddField(
            model_name='adhdcontent',
            name='activity_name',
            field=models.CharField(
                blank=True,
                choices=[
                    ('memory_flip', 'Memory Flip'),
                    ('target_pop', 'Target Pop'),
                    ('focus_hunt', 'Focus Hunt'),
                    ('sequence_recall', 'Sequence Recall'),
                    ('colour_conflict', 'Colour Conflict'),
                    ('task_switch', 'Task Switch'),
                ],
                max_length=50,
                null=True,
                verbose_name='Activity Name',
            ),
        ),
        migrations.AlterField(
            model_name='adhdcontent',
            name='file_type',
            field=models.CharField(
                choices=[
                    ('video', 'Video'),
                    ('document', 'Document'),
                    ('file', 'File'),
                    ('activity', 'Activity'),
                ],
                default='video',
                max_length=50,
                verbose_name='File Type',
            ),
        ),
    ]
