import asyncio
import json
import logging
import re
from django.db.models.signals import post_save
from django.dispatch import receiver
from event.models import Event
from .services import IPReputationService

logger = logging.getLogger(__name__)

# IP extraction pattern (IPv4 only for simplicity, could be expanded)
IP_PATTERN = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'

@receiver(post_save, sender=Event)
def enrich_event_with_ip_reputation(sender, instance, created, **kwargs):
    """
    Signal to automatically check IP reputation when an event is saved.
    This function will:
    1. Extract IP addresses from the event data
    2. Check reputation of each IP
    3. Add reputation data to the event if any IPs are malicious
    """
    if not created:
        # Only process new events to avoid duplication
        return
    
    try:
        # Extract IP addresses from event data
        data = instance.data
        all_data = json.dumps(data)
        ip_addresses = set(re.findall(IP_PATTERN, all_data))
        
        if not ip_addresses:
            logger.debug(f"No IP addresses found in event {instance.id}")
            return
            
        logger.info(f"Found {len(ip_addresses)} IP addresses in event {instance.id}")
        
        # Check reputation for each IP
        service = IPReputationService()
        malicious_ips = []
        
        for ip in ip_addresses:
            # Use asyncio to run the async method
            result = asyncio.run(service.check_ip_reputation(ip))
            if result.get('is_malicious'):
                malicious_ips.append({
                    'ip': ip,
                    'reputation': result
                })
        
        # If malicious IPs found, enrich the event data
        if malicious_ips:
            logger.info(f"Found {len(malicious_ips)} malicious IPs in event {instance.id}")
            
            # Add IP reputation data to event 
            if 'attributes' not in data:
                data['attributes'] = {}
                
            if 'cti4bc_enrichment' not in data['attributes']:
                data['attributes']['cti4bc_enrichment'] = {}
                
            data['attributes']['cti4bc_enrichment']['ip_reputation'] = {
                'malicious_ips': malicious_ips,
                'summary': f"Found {len(malicious_ips)} malicious IP addresses"
            }
            
            # Update event without triggering the signal again
            Event.objects.filter(id=instance.id).update(data=data)
            
            logger.info(f"Event {instance.id} enriched with IP reputation data")
        
    except Exception as e:
        logger.error(f"Error enriching event {instance.id} with IP reputation: {str(e)}")
