from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from certsync_training.contract import enabled, mapping
from event.models import Event


class Command(BaseCommand):
    help = "Delete only training organisations' events; dry run unless --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not enabled():
            raise CommandError("Training integration is disabled.")
        scope = Q(pk__in=[])
        for name, prefix in mapping().items():
            scope |= Q(organization__name=name, organization__prefix=prefix)
        events = Event.objects.filter(scope)
        count = events.count()
        self.stdout.write(f"{'Deleting' if options['apply'] else 'Dry run:'} {count} training events")
        if options["apply"]:
            events.delete()
