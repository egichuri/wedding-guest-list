# Generated by Django 3.1.2 on 2020-10-14 10:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_auto_20201013_1537'),
    ]

    operations = [
        migrations.RenameField(
            model_name='invite',
            old_name='confirmed',
            new_name='received',
        ),
    ]