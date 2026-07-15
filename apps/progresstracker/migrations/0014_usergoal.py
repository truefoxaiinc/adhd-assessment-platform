from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0013_faceattentionsession_session_id_default'),
        ('users', '0012_users_is_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserGoal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('goal', models.TextField(blank=True, default='', verbose_name='Goal')),
                ('rating', models.PositiveSmallIntegerField(default=0, verbose_name='Rating')),
                ('is_first', models.BooleanField(default=False, verbose_name='Is First Goal')),
                ('is_last', models.BooleanField(default=False, verbose_name='Is Last Goal')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='goals', to='users.users')),
            ],
            options={
                'verbose_name': 'UserGoal',
                'verbose_name_plural': 'UserGoals',
                'db_table': 'UserGoal',
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='usergoal',
            index=models.Index(fields=['user', 'is_first'], name='user_goal_first_idx'),
        ),
        migrations.AddIndex(
            model_name='usergoal',
            index=models.Index(fields=['user', 'is_last'], name='user_goal_last_idx'),
        ),
    ]
