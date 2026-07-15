from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_users_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='users',
            name='is_first',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='users',
            name='is_last',
            field=models.BooleanField(default=False),
        ),
    ]
