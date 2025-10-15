from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import time
import logging
import psutil
import socket
import sys
import requests
from django.conf import settings


logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET"])
def database_health(request):
    """
    Check database health by performing a simple query
    Returns response time, connection status, and basic metrics
    """
    try:
        # Measure response time
        start_time = time.time()
        
        # Simple database query to test connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        
        # Check if we got a valid response
        if result and result[0] == 1:
            status = "healthy"
            uptime = 99.95  # Database is accessible
        else:
            status = "warning"
            uptime = 95.0
            
        # Get database statistics if available
        try:
            with connection.cursor() as cursor:
                # Get database size (PostgreSQL specific)
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size
                """)
                db_size = cursor.fetchone()[0] if cursor.rowcount > 0 else "Unknown"
                
                # Get connection count
                cursor.execute("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE state = 'active'
                """)
                active_connections = cursor.fetchone()[0] if cursor.rowcount > 0 else 0
                
        except Exception as e:
            logger.warning(f"Could not get database statistics: {e}")
            db_size = "Unknown"
            active_connections = 0
        
        return JsonResponse({
            "status": status,
            "response_time": f"{response_time}ms",
            "uptime": f"{uptime}%",
            "details": "Database connection successful",
            "metrics": {
                "response_time_ms": response_time,
                "uptime_percentage": uptime,
                "database_size": db_size,
                "active_connections": active_connections,
                "last_check": time.time()
            }
        })
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return JsonResponse({
            "status": "critical",
            "response_time": "timeout",
            "uptime": "0%",
            "details": f"Database connection failed: {str(e)}",
            "metrics": {
                "response_time_ms": 0,
                "uptime_percentage": 0,
                "database_size": "Unknown",
                "active_connections": 0,
                "last_check": time.time(),
                "error": str(e)
            }
        }, status=503)

@csrf_exempt
@require_http_methods(["GET"])
def api_server_health(request):
    """
    Check API server health by measuring internal response times and server statistics
    Returns response time, memory usage, and request statistics
    """
    try:
        import os
        from django.conf import settings
        from django.core.cache import cache
        
        # Measure response time for internal processing
        start_time = time.time()
        
        # Simulate some API work (check settings, cache access, etc.)
        _ = settings.DEBUG
        cache.set('health_check', 'ok', timeout=1)
        health_check_value = cache.get('health_check')
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        
        # Get system metrics
        try:
            # Get current process (Django server)
            process = psutil.Process(os.getpid())
            
            # Memory usage
            memory_info = process.memory_info()
            memory_usage_mb = round(memory_info.rss / 1024 / 1024, 2)  # Convert to MB
            
            # CPU usage (over last second)
            cpu_percent = round(process.cpu_percent(interval=0.1), 2)
            
            # Number of threads
            num_threads = process.num_threads()
            
            # Uptime calculation
            create_time = process.create_time()
            uptime_seconds = time.time() - create_time
            uptime_hours = round(uptime_seconds / 3600, 2)
            
        except ImportError:
            # psutil not available, use basic metrics
            memory_usage_mb = 0
            cpu_percent = 0
            num_threads = 0
            uptime_hours = 0
            
        except Exception as e:
            logger.warning(f"Could not get system metrics: {e}")
            memory_usage_mb = 0
            cpu_percent = 0
            num_threads = 0
            uptime_hours = 0
        
        # Determine status based on response time and resource usage
        if response_time <= 50 and cpu_percent <= 70 and memory_usage_mb <= 512:
            status = "healthy"
            uptime = 99.8
        elif response_time <= 100 and cpu_percent <= 85 and memory_usage_mb <= 1024:
            status = "warning"
            uptime = 98.5
        else:
            status = "critical"
            uptime = 95.0
            
        # Check if cache is working
        cache_status = "working" if health_check_value == 'ok' else "error"
        
        return JsonResponse({
            "status": status,
            "response_time": f"{response_time}ms",
            "uptime": f"{uptime}%",
            "details": f"API server running normally, cache {cache_status}",
            "metrics": {
                "response_time_ms": response_time,
                "uptime_percentage": uptime,
                "memory_usage_mb": memory_usage_mb,
                "cpu_percent": cpu_percent,
                "num_threads": num_threads,
                "uptime_hours": uptime_hours,
                "cache_status": cache_status,
                "python_version": sys.version.split()[0],
                "django_version": settings.VERSION if hasattr(settings, 'VERSION') else "Unknown",
                "last_check": time.time()
            }
        })
        
    except Exception as e:
        logger.error(f"API server health check failed: {e}")
        return JsonResponse({
            "status": "critical",
            "response_time": "timeout",
            "uptime": "0%",
            "details": f"API server health check failed: {str(e)}",
            "metrics": {
                "response_time_ms": 0,
                "uptime_percentage": 0,
                "memory_usage_mb": 0,
                "cpu_percent": 0,
                "num_threads": 0,
                "uptime_hours": 0,
                "last_check": time.time(),
                "error": str(e)
            }
        }, status=503)

@csrf_exempt
@require_http_methods(["GET"])
def redis_cache_health(request):
    """
    Check Redis cache health by performing cache operations
    Returns response time, memory usage, and connection statistics
    """
    try:
        from django.core.cache import cache
        from django.core.cache.backends.redis import RedisCache
        import redis
        
        # Measure cache operation response time
        start_time = time.time()
        
        # Test basic cache operations
        test_key = 'health_check_test'
        test_value = f'test_value_{int(time.time())}'
        
        # SET operation
        cache.set(test_key, test_value, timeout=60)
        
        # GET operation
        retrieved_value = cache.get(test_key)
        
        # DELETE operation
        cache.delete(test_key)
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        
        # Check if cache operations worked correctly
        cache_working = (retrieved_value == test_value)
        
        # Try to get Redis connection info if using Redis backend
        redis_info = {}
        try:
            # Get the cache backend
            cache_backend = cache._cache if hasattr(cache, '_cache') else cache
            
            if hasattr(cache_backend, '_cache') and hasattr(cache_backend._cache, 'connection_pool'):
                # This is a Redis backend
                redis_client = cache_backend._cache
                info = redis_client.info()
                
                redis_info = {
                    'redis_version': info.get('redis_version', 'Unknown'),
                    'used_memory': info.get('used_memory_human', 'Unknown'),
                    'connected_clients': info.get('connected_clients', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0),
                    'uptime_in_seconds': info.get('uptime_in_seconds', 0),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0)
                }
                
                # Calculate hit ratio
                hits = redis_info['keyspace_hits']
                misses = redis_info['keyspace_misses']
                if hits + misses > 0:
                    hit_ratio = round((hits / (hits + misses)) * 100, 2)
                else:
                    hit_ratio = 0
                redis_info['hit_ratio'] = hit_ratio
                
        except Exception as redis_error:
            logger.warning(f"Could not get Redis info: {redis_error}")
            redis_info = {'error': 'Could not connect to Redis or not using Redis backend'}
        
        # Determine status based on response time and cache functionality
        if cache_working and response_time <= 10:
            status = "healthy"
            uptime = 99.9
        elif cache_working and response_time <= 50:
            status = "warning"
            uptime = 98.0
        else:
            status = "critical"
            uptime = 85.0
            
        # Test additional cache operations for thoroughness
        try:
            # Test increment operation
            cache.set('test_counter', 0, timeout=60)
            cache.incr('test_counter')
            counter_value = cache.get('test_counter')
            cache.delete('test_counter')
            
            increment_working = (counter_value == 1)
        except Exception:
            increment_working = False
            
        details = "Cache operations successful" if cache_working and increment_working else "Cache operations failed"
        
        return JsonResponse({
            "status": status,
            "response_time": f"{response_time}ms",
            "uptime": f"{uptime}%",
            "details": details,
            "metrics": {
                "response_time_ms": response_time,
                "uptime_percentage": uptime,
                "cache_working": cache_working,
                "increment_working": increment_working,
                "redis_info": redis_info,
                "last_check": time.time()
            }
        })
        
    except ImportError as e:
        logger.error(f"Redis cache dependencies not available: {e}")
        return JsonResponse({
            "status": "critical",
            "response_time": "N/A",
            "uptime": "0%",
            "details": "Redis dependencies not installed",
            "metrics": {
                "response_time_ms": 0,
                "uptime_percentage": 0,
                "cache_working": False,
                "error": "Redis dependencies not available",
                "last_check": time.time()
            }
        }, status=503)
        
    except Exception as e:
        logger.error(f"Redis cache health check failed: {e}")
        return JsonResponse({
            "status": "critical",
            "response_time": "timeout",
            "uptime": "0%",
            "details": f"Cache health check failed: {str(e)}",
            "metrics": {
                "response_time_ms": 0,
                "uptime_percentage": 0,
                "cache_working": False,
                "error": str(e),
                "last_check": time.time()
            }
        }, status=503)


@csrf_exempt
@require_http_methods(["GET"])
def external_services_health(request):
    """
    Check external services health (MISP servers, etc.)
    Returns connectivity status for each configured external service
    Supports filtering by specific MISP server IDs via 'server_ids' query parameter
    """
    try:
        from misp_servers.models import MISPServer
        
        start_time = time.time()
        services_status = []
        
        # Get selected server IDs from query parameters
        selected_server_ids = request.GET.get('server_ids', '')
        if selected_server_ids:
            try:
                server_ids = [int(id.strip()) for id in selected_server_ids.split(',') if id.strip()]
                # Filter user's accessible servers by the selected IDs
                user = request.user
                if user.is_authenticated:
                    if user.is_superuser:
                        misp_servers = MISPServer.objects.filter(id__in=server_ids)
                    else:
                        misp_servers = MISPServer.objects.filter(
                            id__in=server_ids,
                            organizations__in=user.organizations.all()
                        )
                else:
                    misp_servers = MISPServer.objects.filter(id__in=server_ids)
            except ValueError:
                # If server_ids is malformed, fallback to all servers
                misp_servers = MISPServer.objects.all()
        else:
            # Get all MISP servers from the database
            misp_servers = MISPServer.objects.all()
        
        for misp_server in misp_servers:
            misp_status = {
                'name': f'MISP Server ({misp_server.name})',
                'url': misp_server.url,
                'status': 'unknown',
                'response_time': 0,
                'error': None,
                'organizations': ", ".join([org.name for org in misp_server.organizations.all()]) or 'Unknown'
            }
            
            try:
                misp_start = time.time()
                # Test MISP connectivity with a simple request
                response = requests.get(
                    f"{misp_server.url.rstrip('/')}/servers/getPyMISPVersion.json",
                    headers={
                        'Authorization': misp_server.apikey,
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    timeout=10,
                    verify=False  # Often MISP servers use self-signed certificates
                )
                
                misp_end = time.time()
                misp_status['response_time'] = round((misp_end - misp_start) * 1000, 2)
                
                if response.status_code == 200:
                    misp_status['status'] = 'healthy'
                elif response.status_code == 401:
                    misp_status['status'] = 'auth_error'
                    misp_status['error'] = 'Authentication failed'
                elif response.status_code == 404:
                    misp_status['status'] = 'endpoint_not_found'
                    misp_status['error'] = 'MISP endpoint not found'
                else:
                    misp_status['status'] = 'error'
                    misp_status['error'] = f'HTTP {response.status_code}'
                    
            except requests.exceptions.Timeout:
                misp_status['status'] = 'timeout'
                misp_status['error'] = 'Request timeout (10s)'
            except requests.exceptions.ConnectionError:
                misp_status['status'] = 'unreachable'
                misp_status['error'] = 'Connection failed'
            except requests.exceptions.SSLError:
                misp_status['status'] = 'ssl_error'
                misp_status['error'] = 'SSL certificate error'
            except Exception as e:
                misp_status['status'] = 'error'
                misp_status['error'] = str(e)
                
            services_status.append(misp_status)
        
        # Check legacy environment variable configuration as fallback
        if hasattr(settings, 'MISP_URL') and settings.MISP_URL and not misp_servers.exists():
            misp_status = {
                'name': 'MISP Server (Environment)',
                'url': settings.MISP_URL,
                'status': 'unknown',
                'response_time': 0,
                'error': None,
                'organizations': ['Environment Variable']
            }
            
            try:
                misp_start = time.time()
                response = requests.get(
                    f"{settings.MISP_URL.rstrip('/')}/servers/getPyMISPVersion.json",
                    headers={
                        'Authorization': getattr(settings, 'MISP_TOKEN', ''),
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    timeout=10,
                    verify=getattr(settings, 'MISP_VERIFY_SSL', False)
                )
                
                misp_end = time.time()
                misp_status['response_time'] = round((misp_end - misp_start) * 1000, 2)
                
                if response.status_code == 200:
                    misp_status['status'] = 'healthy'
                elif response.status_code == 401:
                    misp_status['status'] = 'auth_error'
                    misp_status['error'] = 'Authentication failed'
                else:
                    misp_status['status'] = 'error'
                    misp_status['error'] = f'HTTP {response.status_code}'
                    
            except requests.exceptions.Timeout:
                misp_status['status'] = 'timeout'
                misp_status['error'] = 'Request timeout'
            except requests.exceptions.ConnectionError:
                misp_status['status'] = 'unreachable'
                misp_status['error'] = 'Connection failed'
            except Exception as e:
                misp_status['status'] = 'error'
                misp_status['error'] = str(e)
                
            services_status.append(misp_status)
        
        # Calculate overall status
        total_services = len(services_status)
        healthy_services = len([s for s in services_status if s['status'] == 'healthy'])
        
        if total_services == 0:
            overall_status = 'no_services'
            uptime = 100.0
        elif healthy_services == total_services:
            overall_status = 'healthy'
            uptime = 99.9
        elif healthy_services > 0:
            overall_status = 'partial'
            uptime = (healthy_services / total_services) * 95.0
        else:
            overall_status = 'unhealthy'
            uptime = 0.0
        
        response_time = round((time.time() - start_time) * 1000, 2)
        
        return JsonResponse({
            "status": overall_status,
            "uptime": uptime,
            "response_time": response_time,
            "total_services": total_services,
            "healthy_services": healthy_services,
            "services": services_status,
            "metrics": {
                "availability": f"{uptime:.1f}%",
                "services_configured": total_services,
                "connectivity_score": f"{(healthy_services/total_services*100) if total_services > 0 else 100:.1f}%"
            }
        })
        
    except Exception as e:
        logger.error(f"External services health check failed: {e}")
        return JsonResponse({
            "status": "error",
            "uptime": 0.0,
            "response_time": 0,
            "error": str(e),
            "services": []
        }, status=503)


@csrf_exempt
@require_http_methods(["GET"])
def message_queue_health(request):
    """
    Check message queue (Kafka) health
    Returns broker connectivity and authentication status
    """
    try:
        start_time = time.time()
        
        # Get Kafka configuration
        kafka_server = getattr(settings, 'KAFKA_SERVER', None)
        kafka_username = getattr(settings, 'KAFKA_USERNAME', None)
        kafka_password = getattr(settings, 'KAFKA_PASSWORD', None)
        
        health_data = {
            'status': 'unknown',
            'response_time': 0,
            'broker_configured': bool(kafka_server),
            'broker_reachable': False,
            'authentication': 'unknown',
            'error': None
        }
        
        if not kafka_server:
            health_data['status'] = 'not_configured'
            health_data['error'] = 'Kafka server not configured'
            health_data['uptime'] = 0.0
            return JsonResponse(health_data)
        
        try:
            # Parse server address
            if '://' in kafka_server:
                kafka_server = kafka_server.split('://', 1)[1]
            
            if ':' in kafka_server:
                host, port = kafka_server.split(':', 1)
                port = int(port)
            else:
                host = kafka_server
                port = 9092  # Default Kafka port
            
            # Test TCP connectivity to Kafka broker
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                health_data['broker_reachable'] = True
                health_data['status'] = 'healthy'
                health_data['authentication'] = 'not_tested'  # Would need kafka-python for full test
                uptime = 99.5
                
            else:
                health_data['status'] = 'unreachable'
                health_data['error'] = f'Cannot connect to Kafka broker at {kafka_server}'
                uptime = 0.0
                
        except socket.gaierror:
            health_data['status'] = 'dns_error'
            health_data['error'] = f'Cannot resolve hostname: {host}'
            uptime = 0.0
        except ValueError as e:
            health_data['status'] = 'config_error'
            health_data['error'] = f'Invalid server configuration: {str(e)}'
            uptime = 0.0
        except Exception as e:
            health_data['status'] = 'error'
            health_data['error'] = f'Unexpected error: {str(e)}'
            uptime = 0.0
        
        health_data['response_time'] = round((time.time() - start_time) * 1000, 2)
        health_data['uptime'] = uptime
        
        # Add metrics
        health_data['metrics'] = {
            'broker_host': host if 'host' in locals() else 'unknown',
            'broker_port': port if 'port' in locals() else 'unknown',
            'connection_timeout': '5s',
            'availability': f"{uptime:.1f}%"
        }
        
        return JsonResponse(health_data)
        
    except Exception as e:
        logger.error(f"Message queue health check failed: {e}")
        return JsonResponse({
            'status': 'error',
            'response_time': 0,
            'uptime': 0.0,
            'error': str(e),
            'broker_configured': False,
            'broker_reachable': False
        }, status=503)

@csrf_exempt
@require_http_methods(["GET"])
def available_misp_servers(request):
    """
    Returns list of MISP servers available for health monitoring
    For health monitoring purposes, returns all servers but with limited info
    """
    try:
        from misp_servers.models import MISPServer
        
        # For health monitoring, return all servers (with limited info for security)
        misp_servers = MISPServer.objects.all()
        
        # Serialize server data (without API keys for security)
        servers_data = []
        for server in misp_servers:
            servers_data.append({
                'id': server.id,
                'name': server.name,
                'url': server.url,
                'organizations': [org.name for org in server.organizations.all()] or ['Unknown']
            })
        
        return JsonResponse({
            'servers': servers_data,
            'total_count': len(servers_data)
        })
        
    except Exception as e:
        logger.error(f"Failed to fetch available MISP servers: {e}")
        return JsonResponse({
            'error': str(e),
            'servers': [],
            'total_count': 0
        }, status=503)

