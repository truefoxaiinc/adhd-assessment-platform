from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('filehandler', '0003_adhdcontent_activity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('progresstracker', '0017_progresstracker_file_type_activity'),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagementActivitySession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_type', models.CharField(default='activity', max_length=50)),
                ('activity_code', models.CharField(choices=[('memory_flip', 'Memory Flip'), ('target_pop', 'Target Pop'), ('focus_hunt', 'Focus Hunt'), ('sequence_recall', 'Sequence Recall'), ('colour_conflict', 'Colour Conflict'), ('task_switch', 'Task Switch')], max_length=50)),
                ('management_day', models.PositiveIntegerField()),
                ('is_assessment', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('started', 'Started'), ('completed', 'Completed'), ('abandoned', 'Abandoned')], default='completed', max_length=50)),
                ('level', models.PositiveIntegerField(default=1)),
                ('difficulty', models.CharField(choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard'), ('expert', 'Expert')], default='easy', max_length=50)),
                ('started_at', models.DateTimeField()),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('session_duration_seconds', models.FloatField(default=0.0)),
                ('target_count', models.PositiveIntegerField(default=0)),
                ('completed_count', models.PositiveIntegerField(default=0)),
                ('correct_count', models.PositiveIntegerField(default=0)),
                ('incorrect_count', models.PositiveIntegerField(default=0)),
                ('missed_count', models.PositiveIntegerField(default=0)),
                ('assisted_count', models.PositiveIntegerField(default=0)),
                ('action_count', models.PositiveIntegerField(default=0)),
                ('average_response_time_ms', models.FloatField(default=0.0)),
                ('accuracy_rate', models.FloatField(default=0.0)),
                ('completion_rate', models.FloatField(default=0.0)),
                ('response_control_score', models.FloatField(default=0.0)),
                ('speed_score', models.FloatField(default=0.0)),
                ('attention_score', models.FloatField(default=0.0)),
                ('performance_score', models.FloatField(default=0.0)),
                ('final_score', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('content', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_sessions', to='filehandler.adhdcontent')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='management_activity_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ManagementActivitySession',
                'verbose_name_plural': 'ManagementActivitySessions',
                'db_table': 'ManagementActivitySession',
            },
        ),
        migrations.AddIndex(
            model_name='managementactivitysession',
            index=models.Index(fields=['user', '-created_at'], name='activity_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='managementactivitysession',
            index=models.Index(fields=['user', 'management_day', 'activity_code'], name='activity_user_day_code_idx'),
        ),
    ]
