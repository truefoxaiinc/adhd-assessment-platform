from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('assessment', '0015_selfassessmentquestions_age_group'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='selfassessmentquestions',
            new_name='SelfAssessm_age_gro_44412f_idx',
            old_name='SelfAssess_age_gro_9eab1a_idx',
        ),
    ]
