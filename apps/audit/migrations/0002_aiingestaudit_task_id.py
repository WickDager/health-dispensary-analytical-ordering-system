from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiingestaudit",
            name="task_id",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
    ]
