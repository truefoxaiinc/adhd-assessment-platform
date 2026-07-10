# Generated manually for JWT account-state enforcement.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_rename_oauthaccoun_user_id_58db21_idx_oauthaccoun_user_id_70a8db_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='users',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
