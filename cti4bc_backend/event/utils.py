from django.conf import settings
from kafka import KafkaConsumer, TopicPartition
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def consume_last_message(topic):
    kafka_url = settings.KAFKA_SERVER
    kafka_username = settings.KAFKA_USERNAME
    kafka_password = settings.KAFKA_PASSWORD
    consumer = KafkaConsumer(
        bootstrap_servers=[kafka_url],
        security_protocol='SASL_PLAINTEXT',
        sasl_mechanism='PLAIN',
        sasl_plain_username=kafka_username,
        sasl_plain_password=kafka_password,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        value_deserializer=lambda x: x.decode('utf-8')
    )
    partition = TopicPartition(topic, 0)
    consumer.assign([partition])
    consumer.seek_to_end(partition)

    try:
        consumer.poll(timeout_ms=1000)
        end_offsets = consumer.end_offsets([partition])
        if partition not in end_offsets or end_offsets[partition] == 0: # Topic does not exist or has no messages
            return None
        consumer.seek(partition, end_offsets[partition] - 1)
        msg = consumer.poll(timeout_ms=1000)
        if msg:
            for tp, messages in msg.items():
                if len(messages) > 0:
                    last_message = messages[-1]
                    json_data = json.loads(last_message.value)
                    return json_data
        else:
            return None
    except KeyboardInterrupt:
        return None
    finally:
        consumer.close()

def parse_alert_message(message):
    """
    Parse incoming alert message (json)
    """
    alert_data = message
    result = {
        'attack_uuid': '',
        'ttp_id': '',
        'src_asset_uuid': '',
        'dst_asset_uuid': '',
        'simulated_or_real': '',
        'attack_name': 'Unknown attack',
        'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        'description': '',
        'ipv4_addr_objects': []
    }

    if alert_data.get('type') == 'bundle' and 'objects' in alert_data:
        # STIX bundle format
        objects = alert_data.get('objects', [])
        identity_obj = None
        observed_data_obj = None
        attack_type_obj = None
        ipv4_addr_objects = []

        for obj in objects:
            obj_type = obj.get('type')
            if obj_type == 'identity':
                identity_obj = obj
            elif obj_type == 'observed-data':
                observed_data_obj = obj
            elif obj_type == 'x-attack-type':
                attack_type_obj = obj
            elif obj_type == 'ipv4-addr':
                ipv4_addr_objects.append(obj)

        # Extract information from observed-data
        if observed_data_obj:
            result['timestamp'] = observed_data_obj.get('created', result['timestamp'])
            ext = observed_data_obj.get('extensions', {}).get('x-observed-data-ext', {})
            result['description'] = ext.get('description', '')

        # Extract information from attack_type object
        if attack_type_obj:
            result['attack_uuid'] = attack_type_obj.get('id', '')
            result['attack_name'] = attack_type_obj.get('user_id', 'Unknown attack')
            
            # Extract MITRE ATT&CK TTP ID if available
            for ref in attack_type_obj.get('external_references', []):
                if ref.get('source_name') == 'mitre-attack':
                    result['ttp_id'] = ref.get('external_id', '')
            
            # Check for simulation information
            sim_ext = attack_type_obj.get('extensions', {}).get('x-simulation-ext', {})
            result['simulated_or_real'] = sim_ext.get('simulation', '')
        
        # Extract source and destination IP addresses
        if len(ipv4_addr_objects) >= 1:
            result['src_asset_uuid'] = ipv4_addr_objects[0].get('value', '')
        if len(ipv4_addr_objects) >= 2:
            result['dst_asset_uuid'] = ipv4_addr_objects[1].get('value', '')

        result['ipv4_addr_objects'] = [ip.get('value', '') for ip in ipv4_addr_objects if ip.get('value')]
        return result
    else:
        # Legacy format
        result.update({
        'attack_uuid': alert_data.get('attack_uuid', ''),
        'ttp_id': alert_data.get('ttp_id', ''),
        'src_asset_uuid': alert_data.get('src_asset_uuid', ''),
        'dst_asset_uuid': alert_data.get('dst_asset_uuid', ''),
        'simulated_or_real': alert_data.get('simulated_or_real', ''),
        'attack_name': alert_data.get('attack_name', 'Unknown attack'),
        'timestamp': alert_data.get('timestamp', result['timestamp']),
        'description': alert_data.get('description', ''),
        })
        return result

def preprocess_soar_message_into_attributes(data):
    """
    Parses the SOAR4BC message of a cacao v2 playbook into MISP attributes.
    Args:
        data (dict): The SOAR4BC message including a 'workflow' key.
    Returns:
        list: A list of MISP attributes.
    """
    attributes = []
    
    # Safely handle the workflow data structure
    workflow = data.get('workflow', {})
    
    # Handle both dictionary and list cases
    if isinstance(workflow, dict):
        # Dictionary case - process normally
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                # Skip if node isn't a dictionary
                continue
                
            attribute = {
                'type': 'text',
                'category': 'Internal reference',
                'value': f"Node ID: {node_id}, Name: {node.get('name', 'Unknown')}, Type: {node.get('type', 'Unknown')}",
                'comment': f"Workflow step details: {node.get('description', 'No description available')}",
                'to_ids': False
            }

            # Add additional relationships for actions
            if node.get('type') == 'action':
                commands = []
                if isinstance(node.get('commands', []), list):
                    commands = ", ".join(
                        cmd.get("type", "unknown") if isinstance(cmd, dict) else str(cmd)
                        for cmd in node.get("commands", [])
                    )
                agent = node.get("agent", "unknown agent")
                attribute["value"] += f", Commands: {commands}, Agent: {agent}"
            
            # Add the next step, if present
            if "on_completion" in node:
                attribute["comment"] += f" Next step: {node['on_completion']}"

            attributes.append(attribute)
    elif isinstance(workflow, list):
        # List case - create simple attributes from the items
        for i, item in enumerate(workflow):
            if isinstance(item, dict):
                # If the item is a dict, extract structured information
                attribute = {
                    'type': 'text',
                    'category': 'Internal reference',
                    'value': f"Node {i}, Name: {item.get('name', 'Unknown')}, Type: {item.get('type', 'Unknown')}",
                    'comment': f"Workflow step details: {item.get('description', 'No description available')}",
                    'to_ids': False
                }
            else:
                # If the item is not a dict, just store its string representation
                attribute = {
                    'type': 'text',
                    'category': 'Internal reference',
                    'value': f"Workflow item {i}: {str(item)}",
                    'comment': f"Workflow item",
                    'to_ids': False
                }
            attributes.append(attribute)
     
    return attributes

def parse_risk_message_to_attributes(risk_message: dict) -> list[dict]:
    """
    Turn a RISK4BC Kafka message into attributes list (category/type/value/comment/to_ids).
    Handles list/dict 'bowtieValues' and list/dict 'cascades'.
    """
    attrs = []

    # bowtieValues: list of dicts OR dict of dicts
    likelihood = None
    consequence = None
    # Extract likelihood and consequence - handle both dictionary and list formats
    bowtie_values = risk_message.get('bowtieValues', [])
    if isinstance(bowtie_values, list) and bowtie_values:
        if isinstance(bowtie_values[0], dict):
            # Dictionary format
            likelihood = bowtie_values[0].get('likelihood')
            consequence = bowtie_values[0].get('consequence')
    elif isinstance(bowtie_values, dict):
        # Handle case where bowtieValues might be a dictionary instead of a list
        for _, v in bowtie_values.items():
            if isinstance(v, dict):
                likelihood = v.get('likelihood')
                consequence = v.get('consequence')
                break
    
    # Add likelihood and consequence to event data
    if likelihood is not None and consequence is not None:
        attrs.append({
            'type': 'text',
            'category': 'Other',
            'value': f'Likelihood: {likelihood}, Consequence: {consequence}',
            'comment': 'Risk assessment values',
            'to_ids': False
        })

    # Add cascade information - safely handle both list and dict types
    cascades = risk_message.get('cascades', [])
    if isinstance(cascades, list):
        for cascade in cascades:
            attrs.append({
                'type': 'text',
                'category': 'Other',
                'value': f'{cascade.get("name", "N/A")}',
                'comment': 'Cascade information',
                'to_ids': False
            })
    elif isinstance(cascades, dict):
        for _, cascade in cascades.items():
            attrs.append({
                'type': 'text',
                'category': 'Other',
                'value': f'Cascade effect: {cascade}',
                'comment': 'Cascade information',
                'to_ids': False
            })
    return attrs