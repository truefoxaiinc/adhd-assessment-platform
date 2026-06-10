# Generated manually because the local Python environment is missing Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['status', '-published_at', '-id'], name='articles_status_905de7_idx'),
        ),
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['status', 'is_featured', '-published_at', '-id'], name='articles_status_71cabc_idx'),
        ),
    ]
