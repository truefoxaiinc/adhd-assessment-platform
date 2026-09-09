from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('assessment', '0015_selfassessmentquestions_age_group'),
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
