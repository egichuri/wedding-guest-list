# Generated by Django 3.1.2 on 2020-11-16 12:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_auto_20201017_1608'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='residence',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]