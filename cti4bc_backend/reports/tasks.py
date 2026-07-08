"""
Asynchronous report generation tasks (executed by the Django-Q2 `qcluster` worker).

The HTTP request only enqueues `generate_report_task`; the potentially long LLM call
runs here, off the request/response cycle, so no Gunicorn worker is blocked.
"""
import logging

from .models import Report
from .llm_factory import LLMProviderFactory

logger = logging.getLogger(__name__)


def generate_report_task(report_id):
    """
    Generate the content of a Report asynchronously.

    Loads the report and its events, runs the configured LLM service, and persists
    the outcome. The service's ``success`` flag is honoured: on failure the report is
    marked ``failed`` with an error message rather than storing the error text as if
    it were a valid report (previous bug: error content saved with HTTP 201).
    """
    try:
        report = Report.objects.get(pk=report_id)
    except Report.DoesNotExist:
        logger.error("generate_report_task: report %s no longer exists", report_id)
        return

    report.status = Report.STATUS_GENERATING
    report.save(update_fields=['status', 'updated_at'])

    try:
        events = list(report.events.all())
        llm_service = LLMProviderFactory.get_configured_llm_service()
        result = llm_service.generate_report(prompt=report.prompt, events=events)

        if result.get('success'):
            report.generated_content = result['content']
            report.tokens_used = result.get('tokens_used')
            report.generation_time = result.get('generation_time')
            report.llm_provider = result.get('provider', 'unknown')
            report.llm_model = result.get('model', 'unknown')
            report.error_message = None
            report.status = Report.STATUS_COMPLETED
        else:
            report.generated_content = ""
            report.generation_time = result.get('generation_time')
            report.llm_provider = result.get('provider')
            report.llm_model = result.get('model')
            report.error_message = result.get('error') or 'LLM generation failed'
            report.status = Report.STATUS_FAILED
            logger.warning("Report %s generation failed: %s", report_id, report.error_message)

        report.save()

    except Exception as exc:  # noqa: BLE001 - we want to record any failure on the report
        logger.exception("Unexpected error generating report %s", report_id)
        report.generated_content = ""
        report.error_message = str(exc)
        report.status = Report.STATUS_FAILED
        report.save(update_fields=['generated_content', 'error_message', 'status', 'updated_at'])
