from django.db import migrations, models
import apps.progresstracker.models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0012_faceattentionsession_zero_metric_defaults'),
    ]

    operations = [
        migrations.AlterField(
            model_name='faceattentionsession',
            name='session_id',
            field=models.CharField(
                default=apps.progresstracker.models.generate_attention_session_id,
                max_length=100,
            ),
        ),
    ]
