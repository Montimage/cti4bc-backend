import httpx
import json
import time
import os
from django.conf import settings
from decouple import config
from event.models import Event
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class OllamaService:
    """Service to interact with Ollama API for report generation"""
    
    def __init__(self, custom_model: str = None):
        # Get Ollama configuration from environment variables
        self.base_url = self._get_ollama_url()
        self.model = custom_model or self._get_ollama_model()
        self.timeout = 300  # 5 minutes timeout for long generations
        
        logger.info(f"OllamaService initialized with model: {self.model} (custom_model={custom_model})")
        
        # Test connection
        self._test_connection()
    
    def _get_ollama_url(self) -> str:
        """Get Ollama URL from configuration"""
        url = None
        
        # 1. Try Django settings first
        url = getattr(settings, 'OLLAMA_URL', None)
        
        # 2. Try decouple config (reads from .env file)
        if not url:
            try:
                url = config('OLLAMA_URL', default=None)
            except Exception:
                pass
        
        # 3. Try direct environment variable
        if not url:
            url = os.environ.get('OLLAMA_URL')
        
        # 4. Default to localhost
        if not url:
            url = 'http://localhost:11434'
            
        return url.rstrip('/')  # Remove trailing slash
    
    def _get_ollama_model(self) -> str:
        """Get Ollama model from configuration"""
        model = None
        
        # 1. Try direct environment variable first (updated by reload_configuration or PUT request)
        model = os.environ.get('OLLAMA_MODEL')
        logger.debug(f"Environment OLLAMA_MODEL: {model}")
        
        # 2. Try Django settings
        if not model:
            model = getattr(settings, 'OLLAMA_MODEL', None)
            logger.debug(f"Django settings OLLAMA_MODEL: {model}")
        
        # 3. Try decouple config (reads from .env file) as fallback
        if not model:
            try:
                model = config('OLLAMA_MODEL', default=None)
                logger.debug(f"Decouple config OLLAMA_MODEL: {model}")
            except Exception as e:
                logger.debug(f"Error reading OLLAMA_MODEL from decouple: {e}")
        
        # 4. Default model
        if not model:
            model = 'llama3.1:8b'
            logger.debug(f"Using default OLLAMA_MODEL: {model}")
        
        logger.info(f"_get_ollama_model() returning: {model}")
        return model
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available models from Ollama
        
        Returns:
            List of available model names
        """
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    
                    for model in data.get('models', []):
                        model_name = model.get('name', '')
                        if model_name:
                            models.append(model_name)
                    
                    return models
                else:
                    logger.error(f"Failed to get models from Ollama: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting available models: {str(e)}")
            return []

    def _test_connection(self):
        """Test connection to Ollama server"""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/api/version")
                if response.status_code != 200:
                    raise ConnectionError(f"Ollama server not responding: {response.status_code}")
                
                # Log connection info
                version_info = response.json() if response.status_code == 200 else {}
                logger.info(f"Successfully connected to Ollama server at {self.base_url}")
                logger.info(f"Ollama version: {version_info.get('version', 'unknown')}")
                logger.info(f"Using model: {self.model}")
                
        except Exception as e:
            logger.error(f"Failed to connect to Ollama server at {self.base_url}")
            logger.error(f"Error details: {str(e)}")
            logger.info("Troubleshooting tips:")
            logger.info("- For local development: Ensure Ollama is running on localhost:11434")
            logger.info("- For Kubernetes: Check if service 'open-webui-ollama' is accessible")
            logger.info("- Verify OLLAMA_URL environment variable is correctly set")
            raise ConnectionError(
                f"Cannot connect to Ollama server at {self.base_url}. "
                f"Please ensure Ollama is running and accessible. Error: {str(e)}"
            )
    
    def generate_report(self, prompt: str, events: List[Event]) -> Dict[str, Any]:
        """
        Generate a report using Ollama based on prompt and events data
        
        Args:
            prompt: User-provided prompt for report generation
            events: List of Event objects to analyze
            
        Returns:
            Dict containing generated content, tokens used, and generation time
        """
        start_time = time.time()
        
        try:
            # Build context from events
            events_context = self._build_events_context(events)
            
            # Construct full prompt with context
            full_prompt = self._construct_full_prompt(prompt, events_context)
            
            # Generate content with Ollama
            response_text = self._call_ollama_api(full_prompt)
            
            # Calculate generation time
            generation_time = time.time() - start_time
            
            return {
                'content': response_text,
                'tokens_used': self._estimate_tokens(full_prompt + response_text),
                'generation_time': generation_time,
                'success': True,
                'provider': 'ollama',
                'model': self.model
            }
            
        except Exception as e:
            logger.error(f"Error generating report with Ollama: {str(e)}")
            return {
                'content': f"Error generating report with Ollama: {str(e)}",
                'tokens_used': 0,
                'generation_time': time.time() - start_time,
                'success': False,
                'error': str(e),
                'provider': 'ollama',
                'model': self.model
            }
    
    def _call_ollama_api(self, prompt: str) -> str:
        """Make API call to Ollama"""
        # Adjust parameters based on model size
        # Larger models need different settings for optimal performance
        is_large_model = any(size in self.model.lower() for size in ['34b', '27b', '70b', '32b'])
        
        options = {
            "temperature": 0.7,
            "num_predict": 2048,  # Max tokens to generate
            "top_p": 0.9,
            "top_k": 40
        }
        
        # For larger models, reduce some parameters to improve performance
        if is_large_model:
            options.update({
                "num_predict": 1500,  # Slightly reduce max tokens for faster generation
                "top_k": 20,  # Reduce top_k for more focused responses
                "temperature": 0.5  # Lower temperature for more consistent responses
            })
            logger.info(f"Using optimized settings for large model {self.model}")
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": options
        }
        
        try:
            # Use longer timeout for larger models
            timeout = self.timeout * 2 if is_large_model else self.timeout
            logger.info(f"Using timeout: {timeout}s for model {self.model}")
            
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
                
                result = response.json()
                
                if 'error' in result:
                    raise Exception(f"Ollama generation error: {result['error']}")
                
                return result.get('response', '')
                
        except httpx.TimeoutException:
            timeout_used = timeout if 'timeout' in locals() else self.timeout
            raise Exception(f"Ollama request timed out after {timeout_used} seconds. Try using a smaller model for faster generation.")
        except Exception as e:
            raise Exception(f"Failed to call Ollama API: {str(e)}")
    
    def _build_events_context(self, events: List[Event]) -> str:
        """Build structured context from events data"""
        context_parts = []
        
        for event in events:
            # Base event information
            event_data = {
                'id': event.id,
                'external_id': event.external_id,
                'shared': event.shared,
                'shared_at': event.shared_at.isoformat() if event.shared_at else None,
                'organization': event.organization.name if event.organization else 'Unknown',
                'arrival_time': event.arrival_time.isoformat() if event.arrival_time else None,
            }
            
            # Add the JSON data from the event
            if event.data:
                event_data['event_details'] = event.data
            
            # Add timing information if available
            timing_info = {}
            if event.timeliness:
                timing_info['timeliness'] = str(event.timeliness)
            if event.extension_time:
                timing_info['extension_time'] = str(event.extension_time)
            if event.anon_time:
                timing_info['anon_time'] = str(event.anon_time)
            if event.sharing_speed:
                timing_info['sharing_speed'] = str(event.sharing_speed)
            
            if timing_info:
                event_data['timing_metrics'] = timing_info
            
            # Add reports count if available
            if hasattr(event, 'reports'):
                event_data['previous_reports_count'] = event.reports.count()
            
            context_parts.append(f"Event {event.id}: {json.dumps(event_data, indent=2)}")
        
        return "\n\n".join(context_parts)
    
    def _construct_full_prompt(self, user_prompt: str, events_context: str) -> str:
        """Construct the full prompt with context injection"""
        system_prompt = """You are a cybersecurity analyst expert in CTI (Cyber Threat Intelligence). 
Your task is to analyze security events and generate professional reports based on the provided data.

Please provide your analysis in a clear, structured format using markdown.
Focus on actionable insights and recommendations.
Be concise but thorough in your analysis."""
        
        full_prompt = f"""{system_prompt}

USER REQUEST:
{user_prompt}

EVENTS DATA TO ANALYZE:
{events_context}

Please generate a comprehensive report based on the above information."""
        
        return full_prompt
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of tokens used (approximation: 1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def get_available_models(self) -> List[str]:
        """Get list of available models from Ollama"""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [model['name'] for model in data.get('models', [])]
                return []
        except Exception as e:
            logger.error(f"Error getting Ollama models: {str(e)}")
            return []
    
    def is_model_available(self, model_name: str) -> bool:
        """Check if a specific model is available"""
        available_models = self.get_available_models()
        return model_name in available_models
    
    def get_configuration_info(self) -> Dict[str, Any]:
        """
        Get current Ollama configuration information for debugging
        
        Returns:
            Dict containing configuration details
        """
        config_info = {
            'base_url': self.base_url,
            'model': self.model,
            'timeout': self.timeout,
            'connection_status': 'unknown',
            'server_version': 'unknown',
            'available_models_count': 0,
            'configuration_source': self._get_config_source()
        }
        
        # Test connection and get server info
        try:
            with httpx.Client(timeout=10.0) as client:
                # Get version info
                version_response = client.get(f"{self.base_url}/api/version")
                if version_response.status_code == 200:
                    config_info['connection_status'] = 'connected'
                    version_data = version_response.json()
                    config_info['server_version'] = version_data.get('version', 'unknown')
                else:
                    config_info['connection_status'] = f'error_http_{version_response.status_code}'
                
                # Get models count
                models_response = client.get(f"{self.base_url}/api/tags")
                if models_response.status_code == 200:
                    models_data = models_response.json()
                    config_info['available_models_count'] = len(models_data.get('models', []))
                
        except Exception as e:
            config_info['connection_status'] = f'error: {str(e)}'
            
        return config_info
    
    def _get_config_source(self) -> str:
        """
        Determine where the Ollama URL configuration is coming from
        
        Returns:
            String describing the configuration source
        """
        # Check Django settings
        if hasattr(settings, 'OLLAMA_URL') and settings.OLLAMA_URL:
            return 'django_settings'
        
        # Check .env file via decouple
        try:
            env_url = config('OLLAMA_URL', default=None)
            if env_url:
                return 'env_file'
        except Exception:
            pass
        
        # Check environment variable
        if os.environ.get('OLLAMA_URL'):
            return 'environment_variable'
            
        return 'default_value'
