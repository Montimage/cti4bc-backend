from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from certsync_training.contract import enabled, mapping
from organizations.models import Organization
from misp_servers.models import MISPServer


class Command(BaseCommand):
    help = "Create training organisations and grant their platform MISP destination (no network)."

    def add_arguments(self, parser):
        parser.add_argument("--misp-server-id", type=int, required=True)
        parser.add_argument("--misp-org-id", required=True, help="Fictional CI creator organisation ID in MISP A")

    @transaction.atomic
    def handle(self, *args, **options):
        if not enabled():
            raise CommandError("Enable CERTSYNC_TRAINING_ENABLED and configure CTI4BC_SSO_SECRET first.")
        try:
            server = MISPServer.objects.get(pk=options["misp_server_id"])
        except MISPServer.DoesNotExist:
            raise CommandError("MISP server not found.")
        if server.url.rstrip("/") != settings.CERTSYNC_PLATFORM_MISP_URL.rstrip("/"):
            raise CommandError("The server must be the configured platform MISP A.")
        if not str(options["misp_org_id"]).isdigit() or int(options["misp_org_id"]) < 1:
            raise CommandError("Use the fictional CI's positive MISP organisation ID.")
        for name, prefix in mapping().items():
            if Organization.objects.filter(prefix=prefix).exclude(name=name).exists():
                raise CommandError(f"Prefix {prefix} already belongs to another organisation.")
            org, _ = Organization.objects.update_or_create(name=name, defaults={
                "prefix": prefix, "external_id": str(options["misp_org_id"]),
                "email": "training@hospital.example", "description": "Fictional webinar organisation"})
            server.organizations.add(org)
            self.stdout.write(f"{name} -> {prefix}")
        self.stdout.write("Restart the CTI4BC consumer after adding organisations, before participants run chains.")
