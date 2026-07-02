# Seed the NIS2 sectors (Annex I "essential" + Annex II "important").
from django.db import migrations

ESSENTIAL = "essential"
IMPORTANT = "important"

# (code, name, annex)
SECTORS = [
    ("energy", "Energy", ESSENTIAL),
    ("transport", "Transport", ESSENTIAL),
    ("banking", "Banking", ESSENTIAL),
    ("financial-market-infrastructures", "Financial market infrastructures", ESSENTIAL),
    ("health", "Health", ESSENTIAL),
    ("drinking-water", "Drinking water", ESSENTIAL),
    ("waste-water", "Waste water", ESSENTIAL),
    ("digital-infrastructure", "Digital infrastructure", ESSENTIAL),
    ("ict-service-management", "ICT service management (B2B)", ESSENTIAL),
    ("public-administration", "Public administration", ESSENTIAL),
    ("space", "Space", ESSENTIAL),
    ("postal-courier", "Postal & courier services", IMPORTANT),
    ("waste-management", "Waste management", IMPORTANT),
    ("chemicals", "Chemicals", IMPORTANT),
    ("food", "Food", IMPORTANT),
    ("manufacturing", "Manufacturing", IMPORTANT),
    ("digital-providers", "Digital providers", IMPORTANT),
    ("research", "Research", IMPORTANT),
]


def seed_sectors(apps, schema_editor):
    Sector = apps.get_model("organizations", "Sector")
    for code, name, annex in SECTORS:
        Sector.objects.get_or_create(code=code, defaults={"name": name, "annex": annex})


def unseed_sectors(apps, schema_editor):
    Sector = apps.get_model("organizations", "Sector")
    Sector.objects.filter(code__in=[c for c, _, _ in SECTORS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0008_sector_organization_sectors"),
    ]

    operations = [
        migrations.RunPython(seed_sectors, unseed_sectors),
    ]
