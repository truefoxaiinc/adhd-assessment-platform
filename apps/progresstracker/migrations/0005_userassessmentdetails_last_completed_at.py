from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0004_faceattentionsession'),
    ]

    operations = [
        migrations.AddField(
            model_name='userassessmentdetails',
            name='last_completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Last Completed At'),
        ),
    ]
