import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_q.tasks import async_task

from .models import Report, LLMConfig
from .serializers import ReportListSerializer, ReportDetailSerializer, ReportCreateSerializer
from .llm_factory import LLMProviderFactory
from event.models import Event

logger = logging.getLogger(__name__)


def get_accessible_events(user, event_ids):
    """Return the subset of ``event_ids`` the user is allowed to access."""
    if user.is_staff:
        return Event.objects.filter(id__in=event_ids)
    user_organizations = user.organizations.all()
    return Event.objects.filter(id__in=event_ids, organization__in=user_organizations)


class ReportListCreateView(APIView):
    """
    API View to list all reports for user's organization or create a new report
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get all reports for the user's organizations
        """
        try:
            if request.user.is_staff:
                # Staff users can see all reports
                reports = Report.objects.all()
            else:
                # Regular users can only see reports from their organizations or their own reports
                user_organizations = request.user.organizations.all()
                if user_organizations.exists():
                    reports = Report.objects.filter(
                        Q(user=request.user) |
                        Q(events__organization__in=user_organizations)
                    ).distinct()
                else:
                    reports = Report.objects.filter(user=request.user)

            serializer = ReportListSerializer(reports, many=True)
            return Response({'reports': serializer.data}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Failed to fetch reports")
            return Response({
                'error': 'Failed to fetch reports',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """
        Create a new report and queue its generation as an asynchronous task.

        The LLM call no longer runs inline in the request: the report is created with
        status 'pending', a task is enqueued on the Django-Q2 worker, and HTTP 202 is
        returned immediately. The client polls GET /reports/<id>/ for the final status.
        """
        try:
            serializer = ReportCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Validate user has access to selected events
            events_data = serializer.validated_data['events']
            event_ids = [event.id for event in events_data]
            accessible_events = get_accessible_events(request.user, event_ids)

            if accessible_events.count() != len(set(event_ids)):
                return Response(
                    {'error': 'You can only create reports for events you have access to'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Create the report in a pending state and hand generation to the worker
            report = serializer.save(
                user=request.user,
                status=Report.STATUS_PENDING,
                generated_content="",
            )
            async_task('reports.tasks.generate_report_task', report.id)

            response_serializer = ReportDetailSerializer(report)
            return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            logger.exception("Failed to queue report creation")
            return Response({
                'error': 'Failed to create report',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportDetailView(APIView):
    """
    API View to retrieve, update or delete a specific report
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        """
        Get report instance with permission checking
        """
        if user.is_staff:
            return get_object_or_404(Report, pk=pk)
        else:
            # Users can see their own reports or reports from their organizations
            user_organizations = user.organizations.all()
            return get_object_or_404(
                Report,
                Q(pk=pk) & (
                    Q(user=user) |
                    Q(events__organization__in=user_organizations)
                )
            )

    def get(self, request, pk):
        """
        Retrieve a specific report
        """
        try:
            report = self.get_object(pk, request.user)
            serializer = ReportDetailSerializer(report)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': 'Report not found or access denied',
                'details': str(e)
            }, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        """
        Delete a specific report (only if user created it or is staff)
        """
        try:
            report = self.get_object(pk, request.user)

            # Only allow deletion if user created the report or is staff
            if not request.user.is_staff and report.user != request.user:
                return Response(
                    {'error': 'You can only delete reports you created'},
                    status=status.HTTP_403_FORBIDDEN
                )

            report.delete()
            return Response({'message': 'Report deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.exception("Failed to delete report %s", pk)
            return Response({
                'error': 'Failed to delete report',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegenerateReportView(APIView):
    """
    API View to regenerate a report with a new prompt (asynchronously)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """
        Regenerate a report with a new prompt
        """
        try:
            # Get the report
            if request.user.is_staff:
                report = get_object_or_404(Report, pk=pk)
            else:
                report = get_object_or_404(Report, pk=pk, user=request.user)

            # Get new prompt from request
            new_prompt = request.data.get('prompt')
            if not new_prompt:
                return Response(
                    {'error': 'New prompt is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Re-check the user still has access to every event in this report
            event_ids = list(report.events.values_list('id', flat=True))
            if event_ids:
                accessible_events = get_accessible_events(request.user, event_ids)
                if accessible_events.count() != len(set(event_ids)):
                    return Response(
                        {'error': 'You no longer have access to all events in this report'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            # Reset to pending and queue regeneration (the task updates provider/model too)
            report.prompt = new_prompt
            report.generated_content = ""
            report.error_message = None
            report.status = Report.STATUS_PENDING
            report.save()
            async_task('reports.tasks.generate_report_task', report.id)

            serializer = ReportDetailSerializer(report)
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            logger.exception("Failed to regenerate report %s", pk)
            return Response({
                'error': 'Failed to regenerate report',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LLMManagementView(APIView):
    """
    API View to manage LLM providers and test connections.

    The active configuration is persisted in the LLMConfig singleton (database), so
    changes apply immediately and consistently across every worker and the qcluster
    process — no os.environ mutation, no .env rewriting, no hardcoded paths.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get information about available LLM providers and current configuration
        """
        try:
            current_provider = LLMProviderFactory.get_current_provider()
            current_model = LLMProviderFactory.get_current_model()
            available_providers = LLMProviderFactory.get_available_providers()

            # Test current provider
            current_provider_test = LLMProviderFactory.test_provider(current_provider)

            response_data = {
                'current_provider': current_provider,
                'current_model': current_model,
                'available_providers': available_providers,
                'current_provider_status': current_provider_test,
                'message': f"Currently using {current_provider} with model {current_model}"
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Failed to get LLM provider information")
            return Response({
                'error': 'Failed to get LLM provider information',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """
        Test a specific LLM provider
        """
        try:
            provider_name = request.data.get('provider')
            if not provider_name:
                return Response(
                    {'error': 'Provider name is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            test_result = LLMProviderFactory.test_provider(provider_name)

            if test_result['success']:
                return Response(test_result, status=status.HTTP_200_OK)
            else:
                return Response(test_result, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Failed to test LLM provider")
            return Response({
                'error': 'Failed to test LLM provider',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        """
        Update LLM configuration (provider and, for Ollama, model)
        """
        try:
            # Only staff users can change configuration
            if not request.user.is_staff:
                return Response(
                    {'error': 'Only administrators can change LLM configuration'},
                    status=status.HTTP_403_FORBIDDEN
                )

            provider = request.data.get('provider')
            model = request.data.get('model')

            if not provider:
                return Response(
                    {'error': 'Provider is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate provider
            available_providers = LLMProviderFactory.get_available_providers()
            if provider not in available_providers:
                return Response(
                    {'error': f'Invalid provider. Available: {available_providers}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Persist configuration in the database (single source of truth)
            cfg = LLMConfig.load()
            cfg.provider = provider
            if provider == 'ollama' and model:
                cfg.ollama_model = model
            cfg.save()

            # Drop the per-process service cache so the new config is picked up at once
            LLMProviderFactory.reload_configuration()

            # Test the new configuration (best-effort)
            try:
                test_result = LLMProviderFactory.test_provider(provider)
            except Exception as test_error:
                logger.warning("Failed to test provider %s: %s", provider, test_error)
                test_result = {'status': 'test_failed', 'error': str(test_error)}

            response_data = {
                'message': f'LLM configuration updated to {provider}',
                'provider': provider,
                'test_result': test_result,
                'note': 'Configuration stored in database and applied immediately across all workers.'
            }
            if provider == 'ollama':
                response_data['model'] = cfg.ollama_model
            elif model:
                response_data['model'] = model

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Failed to update LLM configuration")
            return Response({
                'error': 'Failed to update LLM configuration',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        """
        Update only the model for the current provider (Ollama only)
        """
        try:
            # Only staff users can change configuration
            if not request.user.is_staff:
                return Response(
                    {'error': 'Only administrators can change LLM configuration'},
                    status=status.HTTP_403_FORBIDDEN
                )

            model = request.data.get('model')
            if not model:
                return Response(
                    {'error': 'Model is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get current provider
            current_provider = LLMProviderFactory.get_current_provider()

            # Currently only support model change for Ollama
            if current_provider != 'ollama':
                return Response(
                    {'error': f'Model selection is only supported for Ollama provider. Current provider: {current_provider}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Best-effort validation: only reject if Ollama is reachable AND the model
            # is genuinely unknown. If Ollama is briefly down, allow the change instead
            # of blocking the admin (the failure would otherwise surface at generation).
            try:
                from .ollama_service import OllamaService
                temp_service = OllamaService()
                available_models = temp_service.get_available_models()
                if available_models and model not in available_models:
                    return Response(
                        {'error': f'Model "{model}" not available. Available models: {available_models}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                logger.warning("Could not validate Ollama model availability: %s", e)

            # Persist model in the database
            cfg = LLMConfig.load()
            cfg.ollama_model = model
            cfg.save()
            LLMProviderFactory.reload_configuration()

            try:
                test_result = LLMProviderFactory.test_provider(current_provider)
            except Exception as test_error:
                logger.warning("Failed to test provider %s: %s", current_provider, test_error)
                test_result = {'status': 'test_failed', 'error': str(test_error)}

            response_data = {
                'message': f'Model updated to {model}',
                'provider': current_provider,
                'model': model,
                'test_result': test_result,
                'note': 'Model configuration stored in database and applied immediately.'
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Failed to update model configuration")
            return Response({
                'error': 'Failed to update model configuration',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LLMModelsView(APIView):
    """
    API View to get available models for a specific provider
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get available models for the specified provider
        """
        try:
            provider = request.query_params.get('provider')
            if not provider:
                provider = LLMProviderFactory.get_current_provider()

            if provider == 'ollama':
                from .ollama_service import OllamaService
                try:
                    service = OllamaService()
                    models = service.get_available_models()
                    # Use the configured model instead of the service's default model
                    current_model = LLMProviderFactory.get_current_model()

                    return Response({
                        'provider': provider,
                        'available_models': models,
                        'current_model': current_model
                    }, status=status.HTTP_200_OK)

                except Exception as e:
                    return Response({
                        'provider': provider,
                        'available_models': [],
                        'current_model': 'unknown',
                        'error': str(e)
                    }, status=status.HTTP_400_BAD_REQUEST)

            elif provider == 'gemini':
                # GeminiService is pinned to gemini-1.5-flash, so advertise only that
                # (previously it also listed gemini-1.5-pro, which was never actually used).
                return Response({
                    'provider': provider,
                    'available_models': ['gemini-1.5-flash'],
                    'current_model': 'gemini-1.5-flash'
                }, status=status.HTTP_200_OK)

            else:
                return Response({
                    'error': f'Unknown provider: {provider}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Failed to get models")
            return Response({
                'error': 'Failed to get models',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_llm_status(request):
    """
    Get detailed status and configuration information for current LLM provider
    Useful for debugging connection issues
    """
    try:
        current_provider = LLMProviderFactory.get_current_provider()

        if current_provider == 'ollama':
            from .ollama_service import OllamaService
            try:
                service = OllamaService()
                config_info = service.get_configuration_info()

                # Test connection
                try:
                    models = service.get_available_models()
                    connection_status = 'connected'
                    connection_error = None
                except Exception as conn_error:
                    connection_status = 'failed'
                    connection_error = str(conn_error)
                    models = []

                return Response({
                    'provider': current_provider,
                    'status': connection_status,
                    'configuration': config_info,
                    'available_models': models,
                    'error': connection_error
                }, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({
                    'provider': current_provider,
                    'status': 'initialization_failed',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif current_provider == 'gemini':
            return Response({
                'provider': current_provider,
                'status': 'connected',
                'configuration': {
                    'model': 'gemini-1.5-flash',
                    'environment': 'cloud'
                },
                'available_models': ['gemini-1.5-flash'],
                'error': None
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                'error': f'Unknown provider: {current_provider}'
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception("Failed to get LLM status")
        return Response({
            'error': 'Failed to get LLM status',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
