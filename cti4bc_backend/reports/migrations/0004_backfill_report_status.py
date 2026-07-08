"""
Backfill the newly-added ``status`` field for reports created before the async refactor.

Without this, every pre-existing report keeps the column default ('pending'), which
would make the UI show them as perpetually pending and trigger endless polling.
"""
from django.db import migrations


def backfill_status(apps, schema_editor):
    Report = apps.get_model("reports", "Report")

    # Legacy error reports stored their error as the content (old buggy behaviour).
    Report.objects.filter(generated_content__startswith="Error generating").update(
        status="failed",
        error_message="Legacy report generated before the async refactor (error content).",
        generated_content="",
    )

    # Legacy placeholders that never resolved -> mark as failed so they aren't polled.
    Report.objects.filter(generated_content__in=["Generating...", "Regenerating..."]).update(
        status="failed",
        error_message="Legacy report that never completed generation.",
        generated_content="",
    )

    # Anything with real content is a completed report.
    Report.objects.exclude(generated_content="").update(status="completed")


def noop_reverse(apps, schema_editor):
    # Status is derivable and non-destructive to leave in place; nothing to undo.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_llmconfig_report_error_message_report_status_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_status, noop_reverse),
    ]
