# Generated by Django 3.1.2 on 2020-11-16 17:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_auto_20201116_1351'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='invite',
            options={'ordering': ['user__first_name', 'user__last_name']},
        ),
    ]