from django.db import migrations, models


def backfill_question_age_group(apps, schema_editor):
    SelfAssessmentQuestions = apps.get_model('assessment', 'SelfAssessmentQuestions')
    SelfAssessmentQuestions.objects.filter(is_for_adults=True).update(age_group='adult')
    SelfAssessmentQuestions.objects.filter(is_for_adults=False).update(age_group='child')


class Migration(migrations.Migration):

    dependencies = [
        ('assessment', '0014_selfassessmentresult_attempt_dates'),
    ]

    operations = [
        migrations.AddField(
            model_name='selfassessmentquestions',
            name='age_group',
            field=models.CharField(
                blank=True,
                choices=[
                    ('child', 'Child'),
                    ('adolescents', 'Adolescents'),
                    ('adult', 'Adult'),
                ],
                max_length=50,
                null=True,
                verbose_name='Age Group',
            ),
        ),
        migrations.RunPython(backfill_question_age_group, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='selfassessmentquestions',
            index=models.Index(fields=['age_group', 'is_active', '-id'], name='SelfAssess_age_gro_9eab1a_idx'),
        ),
    ]
