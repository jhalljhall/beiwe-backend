# Generated by Django 2.2.19 on 2021-06-09 20:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0060_participantmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='participantfcmhistory',
            name='failure_count',
            field=models.IntegerField(default=0),
        ),
    ]