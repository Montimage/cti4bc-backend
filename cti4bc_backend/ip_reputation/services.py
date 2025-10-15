import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
import ipaddress
import json
import re

from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async
from .models import APIConfiguration, IPReputationRecord

logger = logging.getLogger(__name__)


class IPReputationService:
    """
    Service for checking IP reputation across multiple sources
    """
    CACHE_DURATION = timedelta(hours=6)  # Cache results for 6 hours
    
    def __init__(self):
        # Sources are loaded dynamically when needed
        pass
    
    async def check_ip_reputation(self, ip):
        """
        Check IP reputation from all configured sources and 
        return aggregated results
        """
        if not self._is_valid_ip(ip):
            logger.warning(f"Invalid IP format: {ip}")
            return {"error": "Invalid IP format"}
        
        # Check if we have recent data in the database
        existing_record = await self._get_cached_record(ip)
        if existing_record:
            return self._format_record_response(existing_record)
            
        # If not in cache or cache expired, check external sources
        results = await self._check_external_sources(ip)
        
        # Save results to database
        record = await self._save_reputation_data(ip, results)
        
        return self._format_record_response(record)
    
    def _is_valid_ip(self, ip):
        """Check if the provided string is a valid IP address"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    async def _get_cached_record(self, ip):
        """Get cached IP reputation record if it exists and is not expired"""
        try:
            # Use sync_to_async for the database query
            get_record = sync_to_async(IPReputationRecord.objects.get)
            record = await get_record(ip_address=ip)
            
            # Use timezone-aware datetime for comparison
            now = timezone.now()
            if now - record.last_checked > self.CACHE_DURATION:
                return None
            return record
        except IPReputationRecord.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error retrieving IP record from database: {e}")
            return None
    
    async def _check_external_sources(self, ip):
        """Check IP reputation from all external sources concurrently"""
        results = {
            "sources": {},
            "malicious_counts": 0,
            "total_sources": 0
        }
        
        # Load active sources dynamically
        @sync_to_async
        def get_active_sources():
            active_sources = {}
            try:
                configs = APIConfiguration.objects.filter(is_active=True)
                for config in configs:
                    active_sources[config.name] = {
                        'api_key': config.api_key,
                        'base_url': config.base_url,
                        'description': config.description
                    }
            except Exception as e:
                logger.error(f"Error loading active sources: {e}")
            return active_sources
        
        sources = await get_active_sources()
        
        tasks = []
        for source_name, config in sources.items():
            # Generic approach: create task for any configured source
            tasks.append(self._check_source(ip, source_name, config))
        
        if tasks:
            source_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in source_results:
                if isinstance(result, Exception):
                    logger.error(f"Error checking IP reputation: {result}")
                    continue
                
                source_name = result.get('source')
                if not source_name:
                    continue
                
                results["sources"][source_name] = result
                results["total_sources"] += 1
                if result.get('is_malicious', False):
                    results["malicious_counts"] += 1
        
        return results
    
    async def _save_reputation_data(self, ip, results):
        """Save IP reputation data to database"""
        try:
            # Calculate aggregated threat and confidence scores
            threat_score = 0
            confidence_score = 0
            reported_by = {}
            details = {}
            is_malicious = None
            
            if results["total_sources"] > 0:
                # If any source reports the IP as malicious, consider it malicious
                is_malicious = results["malicious_counts"] > 0
                
                # Calculate overall scores using generic method
                for source_name, source_data in results["sources"].items():
                    if source_data.get('is_malicious', False):
                        reported_by[source_name] = timezone.now().isoformat()
                    
                    # Extract details using generic method
                    details[source_name] = self._extract_source_details(source_name, source_data)
                    
                    # Calculate threat score using generic method
                    source_score = self._calculate_source_score(source_name, source_data)
                    threat_score += source_score
            
                # Average threat score and ensure it's in the 0-100 range
                if results["total_sources"] > 0:
                    threat_score = threat_score / results["total_sources"]
                    
                # Confidence score based on number of sources that provided results
                confidence_score = min(100, results["total_sources"] * 50)
            
            # Create or update record using sync_to_async
            @sync_to_async
            @transaction.atomic
            def update_or_create_record():
                return IPReputationRecord.objects.update_or_create(
                    ip_address=ip,
                    defaults={
                        'is_malicious': is_malicious,
                        'threat_score': threat_score,
                        'confidence_score': confidence_score,
                        'reported_by': reported_by,
                        'details': details,
                        'last_checked': timezone.now()
                    }
                )
            
            record, created = await update_or_create_record()
            return record
            
        except Exception as e:
            logger.error(f"Error saving IP reputation data: {e}")
            return None
    
    def _format_record_response(self, record):
        """Format IP reputation record for API response"""
        if not record:
            return {"error": "Failed to retrieve IP reputation"}
        
        return {
            "ip": record.ip_address,
            "is_malicious": record.is_malicious,
            "threat_score": record.threat_score,
            "confidence_score": record.confidence_score,
            "reported_by": record.reported_by,
            "details": record.details,
            "last_checked": record.last_checked.isoformat(),
            "cached": True  # Indicates this was retrieved from the database
        }

    @staticmethod
    def extract_ip_from_event(event_data):
        """
        Extract source IP addresses from event data
        Returns a list of IPs found
        """
        ips = []

        # Function to extract IPs from a dictionary
        def extract_from_dict(data):
            for key, value in data.items():
                if key.lower() in ['src-ip', 'src_ip', 'source-ip', 'source_ip', 'ip-src', 'ip_src', 'srcip', 'sourceip', 'value']:
                    # Check for direct IP match in values
                    if isinstance(value, str) and IPReputationService._is_valid_ip_string(value):
                        ips.append(value)
                # Special handling for STIX objects
                elif key.lower() == 'type' and value == 'ipv4-addr' and isinstance(data, dict) and 'value' in data:
                    if isinstance(data['value'], str) and IPReputationService._is_valid_ip_string(data['value']):
                        ips.append(data['value'])
                elif isinstance(value, dict):
                    extract_from_dict(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            extract_from_dict(item)

        # Extract from 'Attribute' section which is common in MISP events
        attributes = event_data.get('Attribute', [])
        if isinstance(attributes, list):
            for attr in attributes:
                if isinstance(attr, dict):
                    # Look for IP attributes
                    if attr.get('type') in ['ip-src', 'ip-dst'] and attr.get('value'):
                        if IPReputationService._is_valid_ip_string(attr.get('value')):
                            ips.append(attr.get('value'))

        # Also check in the main event data
        extract_from_dict(event_data)
        
        # Return unique IPs
        return list(set(ips))
    
    @staticmethod
    def _is_valid_ip_string(ip_str):
        """Check if a string is a valid IPv4 address"""
        try:
            ipaddress.IPv4Address(ip_str)
            return True
        except:
            return False
    
    async def _check_source(self, ip, source_name, config):
        """Generic method to check any IP reputation source"""
        try:
            # Load configuration from database for this source
            source_config = await self._get_source_configuration(source_name)
            if not source_config:
                logger.warning(f"No configuration found for source: {source_name}")
                return {
                    "source": source_name,
                    "error": f"No configuration found for {source_name}",
                    "is_malicious": False
                }
            
            # Use generic HTTP request handler
            return await self._make_generic_api_request(ip, source_name, source_config)
            
        except Exception as e:
            logger.error(f"Error checking {source_name}: {e}")
            return {"source": source_name, "error": str(e), "is_malicious": False}

    async def _get_source_configuration(self, source_name):
        """Get configuration for a specific source from database"""
        try:
            @sync_to_async
            def get_config():
                try:
                    config = APIConfiguration.objects.get(name=source_name, is_active=True)
                    return {
                        'api_key': config.api_key,
                        'base_url': config.base_url,
                        'description': config.description
                    }
                except APIConfiguration.DoesNotExist:
                    return None
            
            return await get_config()
        except Exception as e:
            logger.error(f"Error getting configuration for {source_name}: {e}")
            return None

    async def _make_generic_api_request(self, ip, source_name, config):
        """Make a generic API request based on source configuration"""
        try:
            # Prepare request based on source name and configuration
            headers, url, params = self._prepare_request(ip, source_name, config)
            
            async with aiohttp.ClientSession() as session:
                if params:
                    async with session.get(url, headers=headers, params=params) as response:
                        return await self._process_response(response, source_name)
                else:
                    async with session.get(url, headers=headers) as response:
                        return await self._process_response(response, source_name)
                        
        except Exception as e:
            logger.error(f"Error making API request to {source_name}: {e}")
            return {"source": source_name, "error": str(e), "is_malicious": False}

    def _prepare_request(self, ip, source_name, config):
        """Prepare HTTP request parameters based on dynamic configuration"""
        base_url = config['base_url'].rstrip('/')
        api_key = config['api_key']
        
        # Try to parse configuration from description field if it contains JSON
        api_config = {}
        try:
            if config.get('description') and config['description'].strip().startswith('{'):
                api_config = json.loads(config['description'])
        except json.JSONDecodeError:
            pass
        
        # Get configuration with defaults
        url_pattern = api_config.get('url_pattern', '{base_url}/{ip}')
        auth_header_name = api_config.get('auth_header_name', 'X-API-KEY')
        custom_headers = api_config.get('custom_headers', {})
        request_params = api_config.get('request_params', {})
        
        # Build URL using pattern
        url = url_pattern.format(base_url=base_url, ip=ip)
        
        # Build headers
        headers = custom_headers.copy()
        if api_key and auth_header_name:  # Only add auth header if both key and header name exist
            headers[auth_header_name] = api_key
        
        # Build parameters - replace {ip} placeholder in param values
        params = {}
        for key, value in request_params.items():
            if isinstance(value, str):
                params[key] = value.format(ip=ip)
            else:
                params[key] = value
        
        # If no params, set to None for cleaner request
        params = params if params else None
        
        return headers, url, params
    
    async def _process_response(self, response, source_name):
        """Process API response generically"""
        if response.status != 200:
            return {
                "source": source_name,
                "error": f"API error: {response.status}",
                "is_malicious": False
            }
        
        try:
            data = await response.json()
            return self._parse_response_data(data, source_name)
        except Exception as e:
            logger.error(f"Error parsing response from {source_name}: {e}")
            return {
                "source": source_name,
                "error": f"Error parsing response: {e}",
                "is_malicious": False
            }

    def _parse_response_data(self, data, source_name):
        """Parse response data with source-specific logic"""
        try:
            # Source-specific parsing
            if source_name.lower() == 'abuseipdb':
                # AbuseIPDB response format
                if 'data' in data:
                    abuse_data = data['data']
                    confidence = abuse_data.get('abuseConfidencePercentage', 0)
                    is_malicious = confidence > 25  # Consider malicious if confidence > 25%
                    
                    return {
                        "source": source_name,
                        "is_malicious": is_malicious,
                        "score": confidence,
                        "additional_info": {
                            "country_code": abuse_data.get('countryCode'),
                            "usage_type": abuse_data.get('usageType'),
                            "isp": abuse_data.get('isp'),
                            "total_reports": abuse_data.get('totalReports', 0),
                            "is_whitelisted": abuse_data.get('isWhitelisted', False)
                        },
                        "raw_data": data
                    }
                    
            elif source_name.lower() == 'virustotal':
                # VirusTotal response format
                if 'data' in data and 'attributes' in data['data']:
                    attributes = data['data']['attributes']
                    last_analysis_stats = attributes.get('last_analysis_stats', {})
                    malicious_count = last_analysis_stats.get('malicious', 0)
                    suspicious_count = last_analysis_stats.get('suspicious', 0)
                    total_engines = sum(last_analysis_stats.values()) if last_analysis_stats else 1
                    
                    # Calculate malicious percentage
                    threat_percentage = ((malicious_count + suspicious_count) / total_engines) * 100 if total_engines > 0 else 0
                    is_malicious = malicious_count > 0 or threat_percentage > 10
                    
                    return {
                        "source": source_name,
                        "is_malicious": is_malicious,
                        "score": threat_percentage,
                        "additional_info": {
                            "malicious_engines": malicious_count,
                            "suspicious_engines": suspicious_count,
                            "total_engines": total_engines,
                            "country": attributes.get('country'),
                            "asn": attributes.get('asn'),
                            "network": attributes.get('network')
                        },
                        "raw_data": data
                    }
                    
            elif source_name.lower() == 'alienvault':
                # AlienVault OTX response format
                if 'pulse_info' in data:
                    pulse_info = data['pulse_info']
                    pulse_count = pulse_info.get('count', 0)
                    is_malicious = pulse_count > 0  # If found in any pulses, consider suspicious
                    
                    # Calculate score based on pulse count (normalize to 0-100)
                    score = min(pulse_count * 10, 100) if pulse_count > 0 else 0
                    
                    return {
                        "source": source_name,
                        "is_malicious": is_malicious,
                        "score": score,
                        "additional_info": {
                            "pulse_count": pulse_count,
                            "country": data.get('country_name'),
                            "asn": data.get('asn'),
                            "city": data.get('city')
                        },
                        "raw_data": data
                    }
                    
            # Generic parsing fallback
            is_malicious = self._detect_malicious_indicators(data)
            score = self._extract_generic_score(data)
            additional_info = self._extract_additional_info(data)
            
            return {
                "source": source_name,
                "is_malicious": is_malicious,
                "score": score,
                "additional_info": additional_info,
                "raw_data": data
            }
                
        except Exception as e:
            logger.error(f"Error parsing data from {source_name}: {e}")
            return {
                "source": source_name,
                "error": f"Error parsing data: {e}",
                "is_malicious": False
            }
    
    def _extract_generic_score(self, data):
        """Extract numeric score from response data generically"""
        score_fields = [
            'score', 'reputation', 'reputation_score', 'threat_score', 
            'risk_score', 'confidence', 'confidence_score', 'rating',
            'abuse_confidence', 'malicious_ratio'
        ]
        
        def search_for_score(d):
            if isinstance(d, dict):
                for key, value in d.items():
                    if any(field in key.lower() for field in score_fields):
                        if isinstance(value, (int, float)):
                            # Normalize to 0-100 range
                            if -10 <= value <= 10:
                                return (value + 10) * 5  # Convert range like -3 to +3 to 0-100
                            elif 0 <= value <= 1:
                                return value * 100  # Convert ratio to percentage
                            elif 0 <= value <= 100:
                                return value  # Already in correct range
                            else:
                                return min(100, max(0, abs(value)))
                    
                    # Recursively search nested dictionaries
                    if isinstance(value, dict):
                        nested_score = search_for_score(value)
                        if nested_score is not None:
                            return nested_score
            
            return None
        
        return search_for_score(data) or 0
    
    def _extract_additional_info(self, data):
        """Extract additional useful information from response"""
        info = {}
        
        # Common fields that might be useful
        useful_fields = [
            'country', 'country_code', 'asn', 'organization', 'isp',
            'usage_type', 'total_reports', 'last_seen', 'first_seen',
            'categories', 'tags', 'engines', 'detections'
        ]
        
        def extract_from_dict(d, prefix=""):
            if isinstance(d, dict):
                for key, value in d.items():
                    field_key = f"{prefix}{key}" if prefix else key
                    
                    if any(field in key.lower() for field in useful_fields):
                        if isinstance(value, (str, int, float, bool, list)):
                            info[field_key] = value
                    elif isinstance(value, dict) and len(prefix.split('.')) < 3:  # Limit recursion depth
                        extract_from_dict(value, f"{field_key}.")
        
        extract_from_dict(data)
        return info

    def _detect_malicious_indicators(self, data):
        """Enhanced generic method to detect malicious indicators in API response"""
        # Common field names that indicate malicious status
        malicious_indicators = [
            'is_malicious', 'malicious', 'threat', 'dangerous', 'suspicious',
            'blacklisted', 'blocked', 'bad', 'evil', 'harmful', 'infected',
            'reputation', 'risk', 'abuse', 'spam', 'phishing', 'malware'
        ]
        
        # Positive indicators (higher values = more malicious)
        positive_score_fields = [
            'threat_score', 'risk_score', 'abuse_confidence', 'malicious_count',
            'detection_count', 'report_count'
        ]
        
        # Negative indicators (higher values = less malicious)  
        negative_score_fields = [
            'reputation', 'trust_score', 'clean_count'
        ]
        
        def search_dict(d, path=""):
            if isinstance(d, dict):
                for key, value in d.items():
                    current_path = f"{path}.{key}" if path else key
                    key_lower = key.lower()
                    
                    # Direct boolean indicators
                    if any(indicator in key_lower for indicator in malicious_indicators):
                        if isinstance(value, bool):
                            return value
                        elif isinstance(value, str):
                            malicious_strings = ['true', 'malicious', 'dangerous', 'suspicious', 'bad', 'harmful']
                            return value.lower() in malicious_strings
                    
                    # Numeric score indicators
                    if any(field in key_lower for field in positive_score_fields):
                        if isinstance(value, (int, float)) and value > 0:
                            # For positive scores, threshold varies by field type
                            if 'confidence' in key_lower or 'percentage' in key_lower:
                                return value > 25  # Confidence percentage threshold
                            elif 'count' in key_lower:
                                return value > 0  # Any positive count is suspicious
                            else:
                                return value > 50  # Generic score threshold
                    
                    if any(field in key_lower for field in negative_score_fields):
                        if isinstance(value, (int, float)):
                            # For negative scores (like reputation), low values indicate malicious
                            if 'reputation' in key_lower:
                                return value < -1  # Negative reputation threshold
                            else:
                                return value < 30  # Low trust/clean score threshold
                    
                    # Check for arrays/lists that might indicate threats
                    if isinstance(value, list) and value:
                        threat_list_indicators = ['threats', 'alerts', 'detections', 'reports', 'incidents']
                        if any(indicator in key_lower for indicator in threat_list_indicators):
                            return len(value) > 0
                    
                    # Recursively search nested structures
                    if isinstance(value, dict):
                        result = search_dict(value, current_path)
                        if result is not None:
                            return result
            
            return False
        
        return search_dict(data)
    
    def _calculate_source_score(self, source_name, source_data):
        """Calculate threat score using completely generic approach"""
        # Use the extracted score from _parse_response_data
        if 'score' in source_data:
            return source_data['score']
        
        # Fallback to generic calculation
        return self._calculate_generic_score(source_data)
    
    def _calculate_generic_score(self, source_data):
        """Enhanced generic score calculation"""
        # Look for score in the parsed data first
        if 'score' in source_data:
            return source_data['score']
        
        # Look for common score fields in additional_info
        if 'additional_info' in source_data:
            for key, value in source_data['additional_info'].items():
                if isinstance(value, (int, float)) and any(term in key.lower() for term in ['score', 'confidence', 'reputation']):
                    # Normalize to 0-100 range
                    if 0 <= value <= 1:
                        return value * 100
                    elif 0 <= value <= 100:
                        return value
                    elif -10 <= value <= 10:
                        return (value + 10) * 5
        
        # Fallback: if source says it's malicious, return 75, else 0
        return 75 if source_data.get('is_malicious', False) else 0


    def _extract_source_details(self, source_name, source_data):
        """Extract relevant details from source data using completely generic approach"""
        base_details = {
            "is_malicious": source_data.get('is_malicious', False),
            "checked_at": timezone.now().isoformat(),
            "source": source_name
        }
        
        # Add score if available
        if 'score' in source_data:
            base_details['score'] = source_data['score']
        
        # Add additional info if available
        if 'additional_info' in source_data:
            base_details['additional_info'] = source_data['additional_info']
        
        # Add any error information
        if 'error' in source_data:
            base_details['error'] = source_data['error']
        
        return base_details

