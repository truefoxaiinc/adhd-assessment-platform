from django.db import migrations, models
from django.utils import timezone


def mark_existing_results_completed(apps, schema_editor):
    SelfAssessmentResult = apps.get_model('assessment', 'SelfAssessmentResult')
    SelfAssessmentResult.objects.exclude(result__isnull=True).exclude(result='').update(
        completed_at=timezone.now()
    )


class Migration(migrations.Migration):

    dependencies = [
        ('assessment', '0013_rename_selfassess_is_for__e0aeaa_idx_selfassessm_is_for__dfd489_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='selfassessmentresult',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='Created At'),
        ),
        migrations.AddField(
            model_name='selfassessmentresult',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Completed At'),
        ),
        migrations.RunPython(mark_existing_results_completed, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='selfassessmentresult',
            index=models.Index(fields=['user', '-completed_at'], name='assessment_user_completed_idx'),
        ),
    ]
