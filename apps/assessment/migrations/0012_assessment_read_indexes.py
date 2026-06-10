# Generated manually because the local Python environment is missing Django.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessment', '0011_remove_selfassessmentresult_confirms_adhd_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='selfassessmentquestions',
            index=models.Index(fields=['is_for_adults', 'is_active', '-id'], name='SelfAssess_is_for__e0aeaa_idx'),
        ),
        migrations.AddIndex(
            model_name='selfassessmentresult',
            index=models.Index(fields=['user', '-id'], name='SelfAssess_user_id_1b79e0_idx'),
        ),
        migrations.AddIndex(
            model_name='selfassessmentresponse',
            index=models.Index(fields=['result_entry', 'question'], name='SelfAssess_result__496fad_idx'),
        ),
    ]
