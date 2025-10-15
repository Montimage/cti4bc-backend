"""
Utility functions for loading API configurations from database
"""
from django.core.cache import cache
from django.db import connection


def get_api_configurations():
    """
    Get API configurations from database with caching
    Returns a dictionary with API configurations
    """
    cache_key = 'api_configurations'
    cached_configs = cache.get(cache_key)
    
    if cached_configs is not None:
        return cached_configs
    
    try:
        # Use raw SQL to avoid model import issues during settings loading
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name, api_key, base_url, is_active 
                FROM ip_reputation_apiconfiguration 
                WHERE is_active = true
            """)
            rows = cursor.fetchall()
            
            configs = {}
            for row in rows:
                name, api_key, base_url, is_active = row
                configs[name] = {
                    'api_key': api_key,
                    'base_url': base_url,
                    'is_active': is_active
                }
                
        # Cache for 5 minutes
        cache.set(cache_key, configs, 300)
        return configs
        
    except Exception:
        # If database doesn't exist yet or table doesn't exist, return empty dict
        return {}


def get_api_key(service_name):
    """
    Get API key for a specific service
    """
    configs = get_api_configurations()
    return configs.get(service_name, {}).get('api_key', '')


def invalidate_api_cache():
    """
    Invalidate the API configuration cache
    Call this when API configurations are updated
    """
    cache.delete('api_configurations')
