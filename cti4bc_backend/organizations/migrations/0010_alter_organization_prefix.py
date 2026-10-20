# Same name and content as the migration already applied on the VPS deployment
# (simulator docs/cti4bc-modifications.md, modification 1), so Django there
# sees it as applied.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0009_seed_nis2_sectors'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='prefix',
            field=models.CharField(max_length=32, unique=True),
        ),
    ]
