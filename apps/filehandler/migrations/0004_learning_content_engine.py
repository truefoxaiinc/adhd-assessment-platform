import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F


def populate_content_dates(apps, schema_editor):
    content_model = apps.get_model('filehandler', 'AdhdContent')
    content_model.objects.filter(updated_at__isnull=True).update(updated_at=F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('filehandler', '0003_adhdcontent_activity'),
        ('users', '0014_add_apple_oauth_provider'),
    ]

    operations = [
        migrations.AddField(model_name='adhdcontent', name='article_body', field=models.JSONField(blank=True, null=True, verbose_name='Article Body')),
        migrations.AddField(model_name='adhdcontent', name='cover_image', field=models.ImageField(blank=True, null=True, upload_to='adhd_content/covers/', verbose_name='Cover Image')),
        migrations.AddField(model_name='adhdcontent', name='description', field=models.TextField(blank=True, verbose_name='Description')),
        migrations.AddField(model_name='adhdcontent', name='estimated_duration_minutes', field=models.PositiveIntegerField(default=0, verbose_name='Estimated Duration Minutes')),
        migrations.AddField(model_name='adhdcontent', name='published_at', field=models.DateTimeField(blank=True, null=True, verbose_name='Published At')),
        migrations.AddField(model_name='adhdcontent', name='question_mode', field=models.CharField(choices=[('practice', 'Practice'), ('scored', 'Scored')], default='practice', max_length=20, verbose_name='Question Mode')),
        migrations.AddField(model_name='adhdcontent', name='status', field=models.CharField(choices=[('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')], db_index=True, default='published', max_length=20, verbose_name='Status'), preserve_default=False),
        migrations.AddField(model_name='adhdcontent', name='updated_at', field=models.DateTimeField(auto_now=True, null=True, verbose_name='Updated At')),
        migrations.RunPython(populate_content_dates, migrations.RunPython.noop),
        migrations.AlterField(model_name='adhdcontent', name='updated_at', field=models.DateTimeField(auto_now=True, verbose_name='Updated At')),
        migrations.AlterField(model_name='adhdcontent', name='file_type', field=models.CharField(choices=[('article', 'Article'), ('video', 'Video'), ('document', 'Document'), ('file', 'File'), ('activity', 'Activity')], default='video', max_length=50, verbose_name='File Type')),
        migrations.AlterField(model_name='adhdcontent', name='status', field=models.CharField(choices=[('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')], db_index=True, default='published', max_length=20, verbose_name='Status')),
        migrations.AddIndex(model_name='adhdcontent', index=models.Index(fields=['status', 'is_management', 'age_group', 'day'], name='content_list_idx')),
        migrations.CreateModel(
            name='ContentQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_text', models.TextField()),
                ('question_type', models.CharField(choices=[('single_choice', 'Single Choice'), ('multiple_choice', 'Multiple Choice'), ('true_false', 'True/False')], default='single_choice', max_length=30)),
                ('explanation', models.TextField(blank=True)),
                ('display_order', models.PositiveIntegerField(default=1)),
                ('maximum_score', models.PositiveIntegerField(default=1)),
                ('is_required', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('content', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='filehandler.adhdcontent')),
            ],
            options={'ordering': ['display_order', 'id']},
        ),
        migrations.CreateModel(
            name='QuestionOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('option_text', models.CharField(max_length=500)),
                ('is_correct', models.BooleanField(default=False)),
                ('display_order', models.PositiveIntegerField(default=1)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='filehandler.contentquestion')),
            ],
            options={'ordering': ['display_order', 'id']},
        ),
        migrations.CreateModel(
            name='ContentAttempt',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('attempt_number', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('in_progress', 'In Progress'), ('completed', 'Completed'), ('abandoned', 'Abandoned')], default='in_progress', max_length=20)),
                ('score', models.FloatField(default=0.0)),
                ('maximum_score', models.FloatField(default=0.0)),
                ('percentage', models.FloatField(default=0.0)),
                ('passed', models.BooleanField(default=False)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('content', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attempts', to='filehandler.adhdcontent')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='content_attempts', to='users.users')),
            ],
            options={'ordering': ['-started_at']},
        ),
        migrations.CreateModel(
            name='ContentAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_correct', models.BooleanField(default=False)),
                ('awarded_score', models.FloatField(default=0.0)),
                ('answered_at', models.DateTimeField(auto_now_add=True)),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='filehandler.contentattempt')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='answers', to='filehandler.contentquestion')),
                ('selected_options', models.ManyToManyField(blank=True, related_name='selected_answers', to='filehandler.questionoption')),
            ],
        ),
        migrations.AddConstraint(model_name='contentquestion', constraint=models.UniqueConstraint(fields=('content', 'display_order'), name='unique_question_order_per_content')),
        migrations.AddIndex(model_name='contentquestion', index=models.Index(fields=['content', 'is_active', 'display_order'], name='content_question_list_idx')),
        migrations.AddConstraint(model_name='questionoption', constraint=models.UniqueConstraint(fields=('question', 'display_order'), name='unique_option_order_per_question')),
        migrations.AddConstraint(model_name='contentattempt', constraint=models.UniqueConstraint(fields=('user', 'content', 'attempt_number'), name='unique_user_content_attempt')),
        migrations.AddIndex(model_name='contentattempt', index=models.Index(fields=['user', 'content', 'status'], name='user_content_attempt_idx')),
        migrations.AddConstraint(model_name='contentanswer', constraint=models.UniqueConstraint(fields=('attempt', 'question'), name='unique_answer_per_attempt_question')),
    ]
