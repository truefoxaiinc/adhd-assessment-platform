from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            'assessment',
            '0016_rename_selfassess_age_gro_9eab1a_idx_selfassessm_age_gro_44412f_idx',
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name='selfassessmentresponse',
            name='response',
            field=models.CharField(
                blank=True,
                choices=[
                    ('4', 'Never'),
                    ('3', 'Rarely'),
                    ('2', 'Sometimes'),
                    ('1', 'Often'),
                    ('0', 'Very Often'),
                ],
                default='4',
                max_length=300,
                null=True,
                verbose_name='Response',
            ),
        ),
    ]
