from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="TokenReceipt", fields=[
            ("jti", models.CharField(max_length=128, primary_key=True, serialize=False)),
            ("expires_at", models.DateTimeField(db_index=True)),
        ]),
        migrations.CreateModel(name="PlatformIdentity", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("subject", models.CharField(max_length=100, unique=True)),
            ("session", models.CharField(max_length=32)),
            ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ]),
    ]
