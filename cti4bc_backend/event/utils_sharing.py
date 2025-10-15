from cti4bc import misp
import asyncio
from kafka import KafkaProducer
from kafka.errors import KafkaError
import logging
from django.conf import settings
import json

logger = logging.getLogger(__name__)

async def _share_to_misp(server_id, server_name, server_url, server_api_key, data):
    """
    Share one event to a single MISP server (async)
    """
    try:
        misp.configure(url=server_url, api_key=server_api_key)
        await misp.event.add({'Event': data})
        return {
            'server_id': server_id,
            'server_name': server_name,
            'success': True,
            'message': 'Shared successfully'
        }
    except Exception as e:
        print(f"Error sharing to MISP server {server_name}: {e}")
        return {
            'server_id': server_id,
            'server_name': server_name,
            'success': False,
            'message': str(e)
        }

async def _share_to_org_topic(org_id, org_name, org_prefix, data):
    """
    Sharing event to remote organization Kafka topic
    """
    topic = f"{org_prefix}.{settings.CTI_REMOTE_TOPIC}"
    try:
        await asyncio.to_thread(produce_message, topic, data)
        print(f"Sharing to {topic}")
        return {
            'server_id': org_id,
            'server_name': f"{org_name} (org topic)",
            'success': True,
            'message': 'Shared successfully'
        }
    except Exception as e:
        return {
            'server_id': org_id,
            'server_name': f"{org_name} (org topic)",
            'success': False,
            'message': str(e)
        }

async def _run_sharing_tasks(misp_servers, orgs, data):
    """
    Creates tasks for both MISP and Organization sharing and runs them concurrently
    """
    tasks = []
    for server in misp_servers:
        tasks.append(asyncio.create_task(_share_to_misp(server['id'], server['name'], server['url'], server['api_key'], data)))
    
    for org in orgs:
        tasks.append(asyncio.create_task(_share_to_org_topic(org['id'], org['name'], org['prefix'], data)))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

def share_all(misp_servers, orgs, data):
    """
    Main function to share event to all configured MISP servers and organizations
    """
    results = asyncio.run(_run_sharing_tasks(misp_servers, orgs, data))

    summary = {
        'attempted': len(results),
        'succeeded': sum(1 for r in results if r.get('success')),
        'failed': sum(1 for r in results if not r.get('success'))
    }
    return results, summary

def produce_message(topic, message):
    kafka_url = settings.KAFKA_SERVER
    kafka_username = settings.KAFKA_USERNAME
    kafka_password = settings.KAFKA_PASSWORD

    producer = KafkaProducer(
        bootstrap_servers=kafka_url,
        security_protocol='SASL_PLAINTEXT',
        sasl_mechanism='PLAIN',
        sasl_plain_username=kafka_username,
        sasl_plain_password=kafka_password,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    try:
        future = producer.send(topic, message)
        record_metadata = future.get(timeout=10) # Wait for message delivery confirmation
        logger.info(f'Message delivered to {record_metadata.topic} [{record_metadata.partition}]')
    
    except KafkaError as e:
        logger.error(f'Failed to produce message: {e}')
    except Exception as e:
        logger.exception('An unexpected error occurred while producing the message')
    finally:
        producer.close()