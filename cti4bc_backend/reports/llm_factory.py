"""
LLM Factory for managing different Language Model providers
"""
import os
import logging
from django.conf import settings
from decouple import config
from typing import Union

from .services import GeminiService
from .ollama_service import OllamaService

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Factory class to create LLM service instances based on configuration"""
    
    # Cache for services to avoid recreating them unnecessarily
    _service_cache = {}
    
    SUPPORTED_PROVIDERS = {
        'gemini': GeminiService,
        'ollama': OllamaService,
    }
    
    @classmethod
    def reload_configuration(cls):
        """
        Reload configuration from .env file and clear service cache
        """
        # Clear service cache to force recreation with new config
        cls._service_cache.clear()
        
        # Reload environment variables from .env file
        env_file_path = '/home/mi/bastien/montimage/DYNABIC/cti4bc/cti4bc_backend/.env'
        if os.path.exists(env_file_path):
            # Re-read .env file and update os.environ
            with open(env_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        os.environ[key] = value
        
        # Force reload of decouple config by clearing its cache
        try:
            # Try to clear decouple's internal config cache if it exists
            import importlib
            import decouple
            if hasattr(decouple, '_config'):
                if hasattr(decouple._config, '_config'):
                    decouple._config._config.clear()
            # Force reimport of decouple to reset its state
            importlib.reload(decouple)
        except Exception as e:
            logger.warning(f"Could not clear decouple cache: {e}")
        
        logger.info("LLM configuration reloaded dynamically")
    
    @classmethod
    def get_llm_service(cls) -> Union[GeminiService, OllamaService]:
        """
        Get the configured LLM service instance (with caching)
        
        Returns:
            Instance of the configured LLM service
            
        Raises:
            ValueError: If the provider is not supported
            Exception: If the service cannot be initialized
        """
        provider = cls._get_llm_provider().lower()
        
        # Check cache first
        if provider in cls._service_cache:
            return cls._service_cache[provider]
        
        if provider not in cls.SUPPORTED_PROVIDERS:
            logger.warning(f"Unsupported LLM provider '{provider}', falling back to 'gemini'")
            provider = 'gemini'
        
        try:
            service_class = cls.SUPPORTED_PROVIDERS[provider]
            service_instance = service_class()
            
            # Cache the service
            cls._service_cache[provider] = service_instance
            
            logger.info(f"Successfully initialized {provider} LLM service")
            return service_instance
            
        except Exception as e:
            logger.error(f"Failed to initialize {provider} service: {str(e)}")
            
            # Try fallback to Gemini if Ollama fails
            if provider != 'gemini':
                logger.info("Attempting fallback to Gemini service...")
                try:
                    fallback_service = GeminiService()
                    logger.info("Successfully initialized fallback Gemini service")
                    return fallback_service
                except Exception as fallback_error:
                    logger.error(f"Fallback to Gemini also failed: {str(fallback_error)}")
            
            raise Exception(f"Cannot initialize any LLM service. Last error: {str(e)}")
    
    @classmethod
    def _get_llm_provider(cls) -> str:
        """Get LLM provider from configuration"""
        provider = None
        
        # 1. Try direct environment variable first (updated by reload_configuration)
        provider = os.environ.get('LLM_PROVIDER')
        
        # 2. Try Django settings  
        if not provider:
            provider = getattr(settings, 'LLM_PROVIDER', None)
        
        # 3. Try decouple config (reads from .env file) as fallback
        if not provider:
            try:
                provider = config('LLM_PROVIDER', default=None)
            except Exception:
                pass
        
        # 4. Default to gemini
        if not provider:
            provider = 'gemini'
            
        return provider
    
    @classmethod
    def get_available_providers(cls) -> list:
        """Get list of available LLM providers"""
        return list(cls.SUPPORTED_PROVIDERS.keys())
    
    @classmethod
    def get_current_provider(cls) -> str:
        """Get the currently configured provider"""
        return cls._get_llm_provider().lower()
    
    @classmethod
    def test_provider(cls, provider_name: str) -> dict:
        """
        Test if a provider can be initialized successfully
        
        Args:
            provider_name: Name of the provider to test
            
        Returns:
            Dict with test results
        """
        if provider_name not in cls.SUPPORTED_PROVIDERS:
            return {
                'success': False,
                'error': f"Provider '{provider_name}' is not supported",
                'available_providers': cls.get_available_providers()
            }
        
        try:
            service_class = cls.SUPPORTED_PROVIDERS[provider_name]
            service_instance = service_class()
            
            # For Ollama, also check available models
            extra_info = {}
            if hasattr(service_instance, 'get_available_models'):
                models = service_instance.get_available_models()
                extra_info['available_models'] = models
                extra_info['current_model'] = getattr(service_instance, 'model', 'unknown')
            
            return {
                'success': True,
                'provider': provider_name,
                'message': f"{provider_name} service initialized successfully",
                **extra_info
            }
            
        except Exception as e:
            return {
                'success': False,
                'provider': provider_name,
                'error': str(e)
            }
    
    @classmethod
    def get_llm_service_with_model(cls, custom_model: str = None) -> Union[GeminiService, OllamaService]:
        """
        Get LLM service instance with a specific model (bypasses cache)
        
        Args:
            custom_model: Specific model to use (only for Ollama)
            
        Returns:
            Instance of the configured LLM service with the specified model
        """
        provider = cls._get_llm_provider().lower()
        
        if provider not in cls.SUPPORTED_PROVIDERS:
            logger.warning(f"Unsupported LLM provider '{provider}', falling back to 'gemini'")
            provider = 'gemini'
        
        try:
            service_class = cls.SUPPORTED_PROVIDERS[provider]
            
            # For Ollama, pass the custom model
            if provider == 'ollama' and custom_model:
                service_instance = service_class(custom_model=custom_model)
                logger.info(f"Created Ollama service with model: {custom_model}")
            else:
                service_instance = service_class()
                logger.info(f"Created {provider} service with default configuration")
            
            return service_instance
            
        except Exception as e:
            logger.error(f"Failed to initialize {provider} service with custom model: {str(e)}")
            
            # Try fallback to Gemini if Ollama fails
            if provider != 'gemini':
                logger.info("Attempting fallback to Gemini service...")
                try:
                    fallback_service = GeminiService()
                    logger.info("Successfully initialized fallback Gemini service")
                    return fallback_service
                except Exception as fallback_error:
                    logger.error(f"Fallback to Gemini also failed: {str(fallback_error)}")
            
            raise Exception(f"Cannot initialize any LLM service. Last error: {str(e)}")
    
    @classmethod
    def get_configured_llm_service(cls) -> Union[GeminiService, OllamaService]:
        """
        Get LLM service instance with the currently configured model
        
        Returns:
            Instance of the configured LLM service with the configured model
        """
        provider = cls._get_llm_provider().lower()
        
        if provider == 'ollama':
            # Get the currently configured model
            current_model = cls.get_current_model()
            cache_key = f"{provider}_{current_model}"
            
            # Check if we have this specific provider+model combination in cache
            if cache_key in cls._service_cache:
                logger.info(f"get_configured_llm_service() - Using cached Ollama service with model: {current_model}")
                return cls._service_cache[cache_key]
            
            # Create new service with the current model
            logger.info(f"get_configured_llm_service() - Creating new Ollama service with model: {current_model}")
            service = cls.get_llm_service_with_model(current_model)
            
            # Cache it with the provider+model key
            cls._service_cache[cache_key] = service
            
            return service
        else:
            # For other providers, use the default service
            logger.info(f"get_configured_llm_service() - Using {provider} with default configuration")
            return cls.get_llm_service()

    @classmethod
    def get_current_model(cls) -> str:
        """Get the currently configured model for the current provider"""
        provider = cls._get_llm_provider().lower()
        
        if provider == 'ollama':
            # Get the current model from environment variables
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
            
            # 4. Default to llama3.1:8b
            if not model:
                model = 'llama3.1:8b'
                logger.debug(f"Using default OLLAMA_MODEL: {model}")
            
            logger.info(f"get_current_model() returning: {model}")
            return model
            
        elif provider == 'gemini':
            return 'gemini-1.5-flash'
        
        return 'unknown'


def get_llm_service():
    """
    Convenience function to get the current LLM service
    This is the main function that should be used throughout the application
    """
    return LLMProviderFactory.get_llm_service()
