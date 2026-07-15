from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('progresstracker', '0014_usergoal'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='usergoal',
            name='user_goal_first_idx',
        ),
        migrations.RemoveIndex(
            model_name='usergoal',
            name='user_goal_last_idx',
        ),
        migrations.RemoveField(
            model_name='usergoal',
            name='is_first',
        ),
        migrations.RemoveField(
            model_name='usergoal',
            name='is_last',
        ),
        migrations.RemoveField(
            model_name='usergoal',
            name='updated_at',
        ),
        migrations.AlterField(
            model_name='usergoal',
            name='goal',
            field=models.TextField(verbose_name='Goal'),
        ),
        migrations.AddIndex(
            model_name='usergoal',
            index=models.Index(fields=['user', 'created_at'], name='user_goal_created_idx'),
        ),
    ]
