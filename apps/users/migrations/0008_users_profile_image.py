# Generated manually because the local Python environment is missing Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_users_ai_assessment_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='users',
            name='profile_image',
            field=models.ImageField(blank=True, null=True, upload_to='profile_images/', verbose_name='Profile Image'),
        ),
    ]
