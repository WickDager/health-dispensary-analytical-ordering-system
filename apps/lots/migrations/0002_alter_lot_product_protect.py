from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("lots", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lot",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lots",
                to="catalog.product",
            ),
        ),
    ]
