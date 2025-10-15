import os
import logging
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Report
from .serializers import ReportListSerializer, ReportDetailSerializer, ReportCreateSerializer
from .llm_factory import get_llm_service, LLMProviderFactory
from event.models import Event

logger = logging.getLogger(__name__)


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
            return Response({
                'error': 'Failed to fetch reports',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """
        Create a new report with AI generation
        """
        try:
            serializer = ReportCreateSerializer(data=request.data)
            if serializer.is_valid():
                # Validate user has access to selected events
                events_data = serializer.validated_data['events']
                event_ids = [event.id for event in events_data]
                accessible_events = self._get_accessible_events(request.user, event_ids)
                
                if len(accessible_events) != len(event_ids):
                    return Response(
                        {'error': 'You can only create reports for events you have access to'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Create report instance
                report = serializer.save(user=request.user, generated_content="Generating...")
                
                # Generate content with configured LLM service and model
                llm_service = LLMProviderFactory.get_configured_llm_service()
                generation_result = llm_service.generate_report(
                    prompt=report.prompt,
                    events=list(accessible_events)
                )
                
                # Update report with generated content
                report.generated_content = generation_result['content']
                report.tokens_used = generation_result['tokens_used']
                report.generation_time = generation_result['generation_time']
                report.llm_provider = generation_result.get('provider', 'unknown')
                report.llm_model = generation_result.get('model', 'unknown')
                report.save()
                
                # Return success response
                response_serializer = ReportDetailSerializer(report)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
                
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"ERROR in report creation: {e}")
            import traceback
            traceback.print_exc()
            
            # Provide more specific error messages
            error_message = str(e)
            if "timed out" in error_message.lower():
                error_message = f"Report generation timed out. Large models may take longer to process. Error: {error_message}"
            elif "ollama" in error_message.lower():
                error_message = f"Ollama service error: {error_message}"
            
            return Response({
                'error': 'Failed to create report',
                'details': error_message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_accessible_events(self, user, event_ids):
        """Get events that the user has access to"""
        if user.is_staff:
            return Event.objects.filter(id__in=event_ids)
        else:
            user_organizations = user.organizations.all()
            return Event.objects.filter(
                id__in=event_ids,
                organization__in=user_organizations
            )


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
            return Response({
                'error': 'Failed to delete report',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegenerateReportView(APIView):
    """
    API View to regenerate a report with a new prompt
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
            
            # Update prompt and regenerate
            report.prompt = new_prompt
            report.generated_content = "Regenerating..."
            report.save()
            
            # Generate new content with configured LLM service and model
            llm_service = LLMProviderFactory.get_configured_llm_service()
            generation_result = llm_service.generate_report(
                prompt=report.prompt,
                events=list(report.events.all())
            )
            
            # Update report with new generated content
            report.generated_content = generation_result['content']
            report.tokens_used = generation_result['tokens_used']
            report.generation_time = generation_result['generation_time']
            report.save()
            
            # Return updated report
            serializer = ReportDetailSerializer(report)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Failed to regenerate report',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LLMManagementView(APIView):
    """
    API View to manage LLM providers and test connections
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
            return Response({
                'error': 'Failed to test LLM provider',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request):
        """
        Update LLM configuration (provider and model)
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
            
            # Update environment variables
            # In Kubernetes/production, we only update runtime environment variables
            # In local development, we also try to update the .env file
            
            try:
                # Always update runtime environment variables first
                os.environ['LLM_PROVIDER'] = provider
                
                # For Ollama, always update the model (use current model as default if none provided)
                if provider == 'ollama':
                    if model:
                        os.environ['OLLAMA_MODEL'] = model
                    # If no model provided, keep the current model in environment
                    elif 'OLLAMA_MODEL' not in os.environ:
                        # Set default model if none exists
                        os.environ['OLLAMA_MODEL'] = 'llama3.1:8b'
                
                # Try to update .env file only in development environment
                env_file_path = os.path.join(settings.BASE_DIR, '.env')
                if not os.path.exists(env_file_path):
                    # Fallback to legacy path for local development
                    env_file_path = '/home/mi/bastien/montimage/DYNABIC/cti4bc/cti4bc_backend/.env'
                
                # Only attempt file writing if file exists and is writable
                if os.path.exists(env_file_path) and os.access(env_file_path, os.W_OK):
                    # Read current .env file
                    with open(env_file_path, 'r') as f:
                        env_lines = f.readlines()
                    
                    # Update or add LLM_PROVIDER
                    provider_updated = False
                    model_updated = False
                    
                    for i, line in enumerate(env_lines):
                        if line.startswith('LLM_PROVIDER='):
                            env_lines[i] = f'LLM_PROVIDER="{provider}"\n'
                            provider_updated = True
                        elif line.startswith('OLLAMA_MODEL=') and model and provider == 'ollama':
                            env_lines[i] = f'OLLAMA_MODEL="{model}"\n'
                            model_updated = True
                    
                    # Add lines if not found
                    if not provider_updated:
                        env_lines.append(f'LLM_PROVIDER="{provider}"\n')
                    
                    if model and provider == 'ollama' and not model_updated:
                        env_lines.append(f'OLLAMA_MODEL="{model}"\n')
                    
                    # Write back to .env file
                    with open(env_file_path, 'w') as f:
                        f.writelines(env_lines)
                        
                    logger.info(f"Updated .env file with provider: {provider}")
                else:
                    logger.info(f"Skipping .env file update (not writable or doesn't exist). Using runtime environment variables only.")
                    
            except Exception as e:
                logger.warning(f"Could not update .env file: {str(e)}. Configuration will be applied to runtime environment only.")
                # Continue execution - runtime env vars are already set
            
            # Reload configuration dynamically
            try:
                LLMProviderFactory.reload_configuration()
                logger.info("LLM configuration reloaded successfully")
            except Exception as reload_error:
                logger.warning(f"Failed to reload LLM configuration: {str(reload_error)}")
            
            # Test the new configuration
            try:
                test_result = LLMProviderFactory.test_provider(provider)
                logger.info(f"Provider {provider} test result: {test_result}")
            except Exception as test_error:
                logger.warning(f"Failed to test provider {provider}: {str(test_error)}")
                test_result = {'status': 'test_failed', 'error': str(test_error)}
            
            response_data = {
                'message': f'LLM configuration updated to {provider}',
                'provider': provider,
                'test_result': test_result,
                'note': 'Configuration updated dynamically. No server restart required.'
            }
            
            if model:
                response_data['model'] = model
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Failed to update LLM configuration',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        """
        Update only the model for the current provider
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
            
            # Validate that the model exists
            try:
                from .ollama_service import OllamaService
                temp_service = OllamaService()
                available_models = temp_service.get_available_models()
                if model not in available_models:
                    return Response(
                        {'error': f'Model "{model}" not available. Available models: {available_models}'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                return Response(
                    {'error': f'Failed to validate model availability: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Update environment variables
            try:
                # Update runtime environment variables
                os.environ['OLLAMA_MODEL'] = model
                
                # Try to update .env file only in development environment
                env_file_path = os.path.join(settings.BASE_DIR, '.env')
                if not os.path.exists(env_file_path):
                    # Fallback to legacy path for local development
                    env_file_path = '/home/mi/bastien/montimage/DYNABIC/cti4bc/cti4bc_backend/.env'
                
                # Only attempt file writing if file exists and is writable
                if os.path.exists(env_file_path) and os.access(env_file_path, os.W_OK):
                    # Read current .env file
                    with open(env_file_path, 'r') as f:
                        env_lines = f.readlines()
                    
                    # Update or add OLLAMA_MODEL
                    model_updated = False
                    
                    for i, line in enumerate(env_lines):
                        if line.startswith('OLLAMA_MODEL='):
                            env_lines[i] = f'OLLAMA_MODEL="{model}"\n'
                            model_updated = True
                            break
                    
                    # Add line if not found
                    if not model_updated:
                        env_lines.append(f'OLLAMA_MODEL="{model}"\n')
                    
                    # Write back to .env file
                    with open(env_file_path, 'w') as f:
                        f.writelines(env_lines)
                        
                    logger.info(f"Updated .env file with model: {model}")
                else:
                    logger.info(f"Skipping .env file update (not writable or doesn't exist). Using runtime environment variables only.")
                    
            except Exception as e:
                logger.warning(f"Could not update .env file: {str(e)}. Configuration will be applied to runtime environment only.")
                # Continue execution - runtime env vars are already set
            
            # Reload configuration dynamically
            try:
                LLMProviderFactory.reload_configuration()
                logger.info("LLM configuration reloaded successfully")
            except Exception as reload_error:
                logger.warning(f"Failed to reload LLM configuration: {str(reload_error)}")
            
            # Test the new configuration
            try:
                test_result = LLMProviderFactory.test_provider(current_provider)
                logger.info(f"Provider {current_provider} test result: {test_result}")
            except Exception as test_error:
                logger.warning(f"Failed to test provider {current_provider}: {str(test_error)}")
                test_result = {'status': 'test_failed', 'error': str(test_error)}
            
            response_data = {
                'message': f'Model updated to {model}',
                'provider': current_provider,
                'model': model,
                'test_result': test_result,
                'note': 'Model configuration updated dynamically. No server restart required.'
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Failed to update model configuration',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request):
        """
        Update LLM configuration (provider and model)
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
            
            # Update environment variables
            # In Kubernetes/production, we only update runtime environment variables
            # In local development, we also try to update the .env file
            
            try:
                # Always update runtime environment variables first
                os.environ['LLM_PROVIDER'] = provider
                
                # For Ollama, always update the model (use current model as default if none provided)
                if provider == 'ollama':
                    if model:
                        os.environ['OLLAMA_MODEL'] = model
                    # If no model provided, keep the current model in environment
                    elif 'OLLAMA_MODEL' not in os.environ:
                        # Set default model if none exists
                        os.environ['OLLAMA_MODEL'] = 'llama3.1:8b'
                
                # Try to update .env file only in development environment
                env_file_path = os.path.join(settings.BASE_DIR, '.env')
                if not os.path.exists(env_file_path):
                    # Fallback to legacy path for local development
                    env_file_path = '/home/mi/bastien/montimage/DYNABIC/cti4bc/cti4bc_backend/.env'
                
                # Only attempt file writing if file exists and is writable
                if os.path.exists(env_file_path) and os.access(env_file_path, os.W_OK):
                    # Read current .env file
                    with open(env_file_path, 'r') as f:
                        env_lines = f.readlines()
                    
                    # Update or add LLM_PROVIDER
                    provider_updated = False
                    model_updated = False
                    
                    for i, line in enumerate(env_lines):
                        if line.startswith('LLM_PROVIDER='):
                            env_lines[i] = f'LLM_PROVIDER="{provider}"\n'
                            provider_updated = True
                        elif line.startswith('OLLAMA_MODEL=') and model and provider == 'ollama':
                            env_lines[i] = f'OLLAMA_MODEL="{model}"\n'
                            model_updated = True
                    
                    # Add lines if not found
                    if not provider_updated:
                        env_lines.append(f'LLM_PROVIDER="{provider}"\n')
                    
                    if model and provider == 'ollama' and not model_updated:
                        env_lines.append(f'OLLAMA_MODEL="{model}"\n')
                    
                    # Write back to .env file
                    with open(env_file_path, 'w') as f:
                        f.writelines(env_lines)
                        
                    logger.info(f"Updated .env file with provider: {provider}")
                else:
                    logger.info(f"Skipping .env file update (not writable or doesn't exist). Using runtime environment variables only.")
                    
            except Exception as e:
                logger.warning(f"Could not update .env file: {str(e)}. Configuration will be applied to runtime environment only.")
                # Continue execution - runtime env vars are already set
            
            # Reload configuration dynamically
            try:
                LLMProviderFactory.reload_configuration()
                logger.info("LLM configuration reloaded successfully")
            except Exception as reload_error:
                logger.warning(f"Failed to reload LLM configuration: {str(reload_error)}")
            
            # Test the new configuration
            try:
                test_result = LLMProviderFactory.test_provider(provider)
                logger.info(f"Provider {provider} test result: {test_result}")
            except Exception as test_error:
                logger.warning(f"Failed to test provider {provider}: {str(test_error)}")
                test_result = {'status': 'test_failed', 'error': str(test_error)}
            
            response_data = {
                'message': f'LLM configuration updated to {provider}',
                'provider': provider,
                'test_result': test_result,
                'note': 'Configuration updated dynamically. No server restart required.'
            }
            
            if model:
                response_data['model'] = model
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Failed to update LLM configuration',
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
                return Response({
                    'provider': provider,
                    'available_models': ['gemini-1.5-flash', 'gemini-1.5-pro'],
                    'current_model': 'gemini-1.5-flash'
                }, status=status.HTTP_200_OK)
            
            else:
                return Response({
                    'error': f'Unknown provider: {provider}'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
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
        return Response({
            'error': 'Failed to get LLM status',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
