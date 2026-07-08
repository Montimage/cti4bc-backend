"""
LLM Factory for managing different Language Model providers.

The active provider/model is stored in the database (``LLMConfig`` singleton) rather
than in the process environment or the .env file. This keeps the configuration
consistent across all workers (Gunicorn + qcluster), removes the hardcoded .env path,
and avoids read-modify-write races on the .env file.
"""
import logging
from typing import Union

from django.conf import settings

from .services import GeminiService
from .ollama_service import OllamaService

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Factory class to create LLM service instances based on configuration"""

    # Per-process cache of service instances. Keys embed the DB-backed config
    # (provider, and model for Ollama), so a configuration change made on any worker
    # is picked up by every worker on its next request (different key -> new instance).
    _service_cache = {}

    SUPPORTED_PROVIDERS = {
        'gemini': GeminiService,
        'ollama': OllamaService,
    }

    @classmethod
    def reload_configuration(cls):
        """Clear the per-process service cache so the next call rebuilds from DB config."""
        cls._service_cache.clear()
        logger.info("LLM service cache cleared; configuration will be re-read from the database")

    # ------------------------------------------------------------------ config

    @classmethod
    def _config(cls):
        # Imported lazily to avoid any import-time coupling with the models layer.
        from .models import LLMConfig
        return LLMConfig.load()

    @classmethod
    def _get_llm_provider(cls) -> str:
        """Get the currently configured provider from the database."""
        provider = (cls._config().provider or 'gemini').lower()
        if provider not in cls.SUPPORTED_PROVIDERS:
            logger.warning("Unsupported LLM provider '%s', falling back to 'gemini'", provider)
            provider = 'gemini'
        return provider

    @classmethod
    def get_available_providers(cls) -> list:
        """Get list of available LLM providers"""
        return list(cls.SUPPORTED_PROVIDERS.keys())

    @classmethod
    def get_current_provider(cls) -> str:
        """Get the currently configured provider"""
        return cls._get_llm_provider()

    @classmethod
    def get_current_model(cls) -> str:
        """Get the currently configured model for the current provider"""
        provider = cls._get_llm_provider()
        if provider == 'ollama':
            return cls._config().ollama_model or 'llama3.1:8b'
        elif provider == 'gemini':
            return getattr(settings, 'GEMINI_MODEL', None) or 'gemini-1.5-flash'
        return 'unknown'

    # ---------------------------------------------------------------- services

    @classmethod
    def get_llm_service(cls) -> Union[GeminiService, OllamaService]:
        """
        Get the configured LLM service instance (with caching).

        Raises:
            Exception: If the configured provider's service cannot be initialised.
                       There is NO silent cross-provider fallback: if Ollama (local)
                       is selected and fails, we do not quietly send data to Gemini
                       (cloud). The caller (async task) records the failure instead.
        """
        provider = cls._get_llm_provider()

        if provider in cls._service_cache:
            return cls._service_cache[provider]

        service_class = cls.SUPPORTED_PROVIDERS[provider]
        service_instance = service_class()
        cls._service_cache[provider] = service_instance
        logger.info("Successfully initialized %s LLM service", provider)
        return service_instance

    @classmethod
    def get_llm_service_with_model(cls, custom_model: str = None) -> Union[GeminiService, OllamaService]:
        """Get an LLM service instance, optionally with a specific Ollama model (no fallback)."""
        provider = cls._get_llm_provider()
        service_class = cls.SUPPORTED_PROVIDERS[provider]

        if provider == 'ollama' and custom_model:
            logger.info("Creating Ollama service with model: %s", custom_model)
            return service_class(custom_model=custom_model)

        logger.info("Creating %s service with default configuration", provider)
        return service_class()

    @classmethod
    def get_configured_llm_service(cls) -> Union[GeminiService, OllamaService]:
        """Get an LLM service instance for the currently configured provider and model."""
        provider = cls._get_llm_provider()

        if provider == 'ollama':
            current_model = cls.get_current_model()
            cache_key = f"{provider}_{current_model}"
            if cache_key in cls._service_cache:
                return cls._service_cache[cache_key]
            service = cls.get_llm_service_with_model(current_model)
            cls._service_cache[cache_key] = service
            return service

        return cls.get_llm_service()

    @classmethod
    def test_provider(cls, provider_name: str) -> dict:
        """Test if a provider can be initialised successfully."""
        if provider_name not in cls.SUPPORTED_PROVIDERS:
            return {
                'success': False,
                'error': f"Provider '{provider_name}' is not supported",
                'available_providers': cls.get_available_providers()
            }

        try:
            service_class = cls.SUPPORTED_PROVIDERS[provider_name]
            service_instance = service_class()

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


def get_llm_service():
    """
    Convenience function to get the current LLM service.
    This is the main function that should be used throughout the application.
    """
    return LLMProviderFactory.get_llm_service()
