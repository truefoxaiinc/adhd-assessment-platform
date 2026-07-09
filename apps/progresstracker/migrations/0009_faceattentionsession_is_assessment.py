from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0008_faceattentionsession_query_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='faceattentionsession',
            name='is_assessment',
            field=models.BooleanField(default=False),
        ),
    ]
