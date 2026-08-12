from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0018_managementactivitysession'),
    ]

    operations = [
        migrations.AddField(
            model_name='faceattentionsession',
            name='avg_sustained_duration',
            field=models.FloatField(default=0.0),
        ),
    ]
