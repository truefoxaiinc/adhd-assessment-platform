import django_ckeditor_5.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('filehandler', '0004_learning_content_engine'),
    ]

    operations = [
        migrations.AddField(
            model_name='adhdcontent',
            name='article_content',
            field=django_ckeditor_5.fields.CKEditor5Field(blank=True, config_name='article', verbose_name='Article Content'),
        ),
    ]
