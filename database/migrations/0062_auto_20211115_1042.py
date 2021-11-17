# Generated by Django 2.2.24 on 2021-11-15 10:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0061_historical_data_qty_stats'),
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
    ]