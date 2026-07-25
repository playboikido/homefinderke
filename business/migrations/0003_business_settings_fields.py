from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0002_add_new_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='is_paused_by_owner',
            field=models.BooleanField(default=False, help_text='Owner-controlled: temporarily hide this listing from the public directory without losing approval.'),
        ),
        migrations.AddField(
            model_name='business',
            name='notify_new_review',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='business',
            name='notify_new_inquiry',
            field=models.BooleanField(default=True),
        ),
    ]