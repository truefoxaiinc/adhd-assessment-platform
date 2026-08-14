from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('filehandler', '0005_adhdcontent_article_content'),
        ('progresstracker', '0020_alter_progresstracker_file_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='contentattempt',
            name='attention_session',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='question_attempt',
                to='progresstracker.faceattentionsession',
            ),
        ),
    ]
