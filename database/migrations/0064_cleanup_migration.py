# Generated by Django 2.2.24 on 2021-11-15 10:42

from django.db import migrations, models


def remove_batch_users(apps, schema_editor):
    Researcher = apps.get_model('database', 'Researcher')
    Researcher.objects.filter(is_batch_user=True).delete()

def remove_batch_users_in_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    
    dependencies = [
        ('database', '0063_auto_20211207_1841'),
    ]
    
    operations = [
        migrations.AlterField(
            model_name='survey',
            name='survey_type',
            field=models.CharField(choices=[('audio_survey', 'audio_survey'), ('tracking_survey', 'tracking_survey'), ('image_survey', 'image_survey')], help_text='What type of survey this is.', max_length=16),
        ),
        migrations.AlterField(
            model_name='surveyarchive',
            name='survey_type',
            field=models.CharField(choices=[('audio_survey', 'audio_survey'), ('tracking_survey', 'tracking_survey'), ('image_survey', 'image_survey')], help_text='What type of survey this is.', max_length=16),
        ),
        migrations.RunPython(remove_batch_users, reverse_code=remove_batch_users_in_reverse),
        migrations.AlterField(
            model_name='participant',
            name='push_notification_unreachable_count',
            field=models.SmallIntegerField(default=0),  # default was accidentally "True", which was coerced to 1
        ),
    ]