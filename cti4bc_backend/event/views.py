from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Event, Organization, EventShareLog
from event_files.models import EventAttachment
import json
from django.conf import settings
from cti4bc import anonymization
from cti4bc import aggregation
from django.shortcuts import get_object_or_404
from datetime import datetime
import pytz
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
from .serializers import EventSerializer, ShareEventSerializer
from .utils import consume_last_message, preprocess_soar_message_into_attributes, parse_risk_message_to_attributes, parse_alert_message
import re
from django.utils import timezone
import concurrent.futures
import os
from event_files.models import EventAttachment
from misp_servers.models import MISPServer
from public_key.models import PublicKey
from .utils_sharing import share_all, produce_message
import logging
from dateutil import parser

logger = logging.getLogger(__name__)

class GetEventsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        # Superusers can see all events
        if request.user.is_staff:
            events = Event.objects.all()
        else:
            # Regular users can only see events from their organizations
            user_organizations = request.user.organizations.all()
            if user_organizations.exists():
                events = Event.objects.filter(organization__in=user_organizations)
            else:
                return JsonResponse({'events': []}, status=200)

        event_data = [{
            'id': event.id, 
            'shared': event.shared, 
            'info': event.data.get('info'), 
            'threat_level_id': event.data.get('threat_level_id'),
            'date': event.arrival_time.strftime('%Y-%m-%d %H:%M:%S') if event.arrival_time else event.data.get('date'),
            'organization': event.organization.name,
            'organization_id': event.organization.id,
            'shared_at': event.shared_at.strftime('%Y-%m-%d %H:%M:%S') if event.shared_at else None} for event in events]
        return JsonResponse({'events': event_data}, status=200)

class GetEventById(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            event = Event.objects.get(id=id)

            # Check permissions - only superusers and organization members can see details
            if not request.user.is_staff:
                user_organizations = request.user.organizations.all()
                if not user_organizations.filter(id=event.organization.id).exists():
                    return Response({'error': 'Unauthorized'}, status=403)

            attachments = EventAttachment.objects.filter(event=event).values(
                'id', 'file', 'uploaded_at', 'uploaded_by__username'
            )

            attachments = [
                {
                    'id': attachment['id'],
                    'file': os.path.basename(attachment['file']),
                    'uploaded_at': attachment['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    'uploaded_by': attachment['uploaded_by__username']
                } for attachment in attachments
            ]
            
            attributes = {}
            if 'Attribute' in event.data:
                attributes = event.data['Attribute']
            
            aware_attributes = attributes.get('AWARE4BC', [])
            risk_attributes = attributes.get('RISK4BC', [])
            soar_attributes = attributes.get('SOAR4BC', [])
            
            all_attributes = []
            all_attributes.extend(aware_attributes)
            all_attributes.extend(risk_attributes)
            all_attributes.extend(soar_attributes)

            response_data = {
                'event': {
                    'id': event.id,
                    'shared': event.shared,
                    'shared_date': event.shared_at.strftime('%Y-%m-%d %H:%M:%S') if event.shared_at else None,
                    'data': event.data,
                },
                'files': list(attachments),
                'attributes': {
                    'all': all_attributes,
                    'aware': aware_attributes,
                    'risk': risk_attributes,
                    'soar': soar_attributes
                }
            }
            return Response(response_data, status=200)
        except Event.DoesNotExist:
            return Response({'error': 'Event not found'}, status=404)



class ShareEventView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, id):
        print(request.data)
        event_backend = get_object_or_404(Event, id=id)
        if not request.user.is_staff:
            user_organizations = request.user.organizations.all()
            if not user_organizations.filter(id=event_backend.organization.id).exists():
                return Response({'error': 'Unauthorized'}, status=403)
            
        serializer = ShareEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        data = serializer.validated_data
    
        # Get the list of MISP server IDs from the request
        misp_server_ids = request.data.get('misp_server_ids', [])
        # Get organization IDs from the request
        org_ids = request.data.get('organization_ids', [])
        
        # If no recipients are specified, return an error
        if not misp_server_ids and not org_ids:
            return Response({'error': 'No recipients specified for sharing.'}, status=400)

        misp_servers_info = []
        if misp_server_ids:  
            # Fetch the MISP server instances      
            misp_servers = MISPServer.objects.filter(id__in=misp_server_ids)
            
            # If no servers were found, return an error
            if not misp_servers.exists():
                return Response({'error': 'No valid MISP servers found with the provided IDs.'}, status=400)

            # Validate that the user has access to all specified MISP servers
            if not request.user.is_staff:
                user_orgs = set(request.user.organizations.all())
                for server in misp_servers:
                    server_orgs = set(server.organizations.all())
                    if user_orgs.isdisjoint(server_orgs):
                        return Response({'error': f'Unauthorized access to MISP server: {server.name}'}, status=403)
            misp_servers_info = [{
                'id': s.id,
                'name': s.name,
                'url': s.url,
                'api_key': s.apikey
            } for s in misp_servers]

        orgs_info = []
        if org_ids:
            # Validate organization IDs
            valid_orgs = Organization.objects.filter(id__in=org_ids)
            if not valid_orgs.exists():
                return Response({'error': 'No valid organizations found with the provided IDs.'}, status=400)
            orgs_info = [{
                'id': o.id,
                'name': o.name,
                'prefix': o.prefix
            } for o in valid_orgs]

        # Existing anonymization logic
        original_attributes = data.get('Attribute', [])
        init_anon_time = datetime.now()

        # Get date and log it
        logging.info(f"Original event date: {data.get('date', 'N/A')}")
        data = anonymization.generelize_date(data)
        # Anonymization module configuration
        if not configure_anonymization_module():
            return Response({'error': 'Required encryption keys are missing. Event not shared.'}, status=400)
        aware_attributes = original_attributes.get('AWARE4BC', [])
        attributes_list = anonymization.process_attributes(aware_attributes)
        finish_anon_time = datetime.now()
        anon_time = finish_anon_time - init_anon_time

        # Add risk and soar attributes to the attributes list
        attributes_list.extend(original_attributes.get('RISK4BC', []))
        attributes_list.extend(original_attributes.get('SOAR4BC', []))

        # Validate and process artifacts to include as MISP attributes
        artifacts_list = data.get('artifacts', [])
        for artifact in artifacts_list:
            if not artifact.get('share', False):
                continue
            try:
                attachment = EventAttachment.objects.get(id=artifact['id'], event = event_backend)
                attachment.public = True
                attachment.save()
                artifact_url = f"{settings.FRONTEND_URL}/download/{attachment.id}"

                attributes_list.append({
                    "type": "link",
                    "value": artifact_url,
                    "category": "External analysis",
                    "comment": "Shared artifact",
                    "to_ids": False,
                })
            except EventAttachment.DoesNotExist:
                continue

        # Create timestamp strings for MISP format
        current_timestamp = int(datetime.now().timestamp())
        
        # Extract and format the date correctly for MISP
        date_value = data.get('date', event_backend.data.get('date', datetime.now().strftime('%Y-%m-%d')))
        # Handle case where date might be an object with 'value' property
        if isinstance(date_value, dict) and 'value' in date_value:
            date_value = date_value['value']
        # Ensure date is in YYYY-MM-DD format for MISP
        if isinstance(date_value, str):
            try:
                # Try to parse and reformat to ensure consistent format
                parsed_date = datetime.strptime(date_value.split(' ')[0], '%Y-%m-%d')
                date_value = parsed_date.strftime('%Y-%m-%d')
            except (ValueError, IndexError):
                # If parsing fails, use current date
                date_value = datetime.now().strftime('%Y-%m-%d')
        else:
            date_value = datetime.now().strftime('%Y-%m-%d')

        # Format data in MISP standard format
        misp_event_data = {
            'org_id': str(event_backend.organization.external_id),
            'distribution': data.get('distribution', '0'),
            'info': data.get('info', event_backend.data.get('info', 'No information available')),
            'orgc_id': str(event_backend.organization.external_id),
            'date': date_value,
            'published': data.get('published', False),
            'analysis': data.get('analysis', '0'),
            'timestamp': str(current_timestamp),
            'sharing_group_id': "1",
            'proposal_email_lock': data.get('proposal_email_lock', False),
            'locked': data.get('locked', False),
            'threat_level_id': data.get('threat_level_id', '1'),
            'publish_timestamp': str(current_timestamp),
            'sighting_timestamp': str(current_timestamp),
            'disable_correlation': data.get('disable_correlation', False),
            'event_creator_email': event_backend.organization.email
        }
        
        # Clean and format attributes for MISP compatibility
        def clean_attribute_for_misp(attr):
            """Clean attribute to ensure MISP compatibility"""
            cleaned_attr = {}
            for key, value in attr.items():
                if isinstance(value, dict) and 'value' in value:
                    cleaned_attr[key] = str(value['value'])
                elif isinstance(value, bool):
                    cleaned_attr[key] = value
                else:
                    cleaned_attr[key] = str(value) if value is not None else ""
            return cleaned_attr

        # Clean all attributes for MISP compatibility
        clean_attributes_list = []
        for attr in attributes_list:
            clean_attr = clean_attribute_for_misp(attr)
            clean_attributes_list.append(clean_attr)

        # Create event data with cleaned attributes
        complete_event_data = dict(misp_event_data)
        complete_event_data['Attribute'] = clean_attributes_list
        
        start_sharing_time = datetime.now()

        sharing_results, summary = share_all(misp_servers_info, orgs_info, complete_event_data)
                
        finish_sharing_time = datetime.now()
        event_backend.sharing_speed = finish_sharing_time - start_sharing_time
        
        # If no successful shares, return an error
        if summary["succeeded"] == 0:
            return Response({
                'error': 'Failed to share event with recipient/s.',
                'details': sharing_results
            }, status=500)
        
        # Use the same UTC as the arrival date for the sharing date
        sharing_time = timezone.now()
        
        # Update event status and create share log
        event_backend.timeliness = sharing_time - event_backend.arrival_time if event_backend.arrival_time else None
        event_backend.anon_time = anon_time
        event_backend.shared = True
        event_backend.shared_at = sharing_time
        event_backend.save()

        # Create share log with the correctly formatted MISP data and the sharing results
        misp_event_data['sharing_results'] = sharing_results
        EventShareLog.objects.create(
            event=event_backend,
            shared_by=request.user,
            data=misp_event_data,
            shared_at=sharing_time
        )

        # Return a success response with details of which servers successfully received the event
        return Response({
            'message': 'Event shared with selected MISP servers.',
            'results': sharing_results
        }, status=200)

def configure_anonymization_module():
    try:
        encryption_key = PublicKey.objects.get(name='CRYPTOGRAPHY')
        encryption_path = encryption_key.file.path
        anonymization._configure(
            crypto_key_path=encryption_path
        )
        return True
    except PublicKey.DoesNotExist:
        logging.warning(f'Failed to configure anonymization module: PublicKey "CRYPTOGRAPHY" not found')
        return False

    
@csrf_exempt # This decorator is used to exempt the view from CSRF verification TODO Delete in production
# Endpoint for aggregation of events
def aggregate(request):
    if request.method == 'POST':
        try:
            # Parse the JSON data from the request body and retrieve the events' ids
            data = json.loads(request.body.decode('utf-8'))
            event_ids = data.get('eventsId', [])
  
            events = Event.objects.filter(id__in=event_ids) # Retrieve the events from the database
            event_ids = [event.id for event in events] # Retrieve ids of found events
            events_data = [event.data for event in events] # Retrieve data of found events

            new_event = aggregation.aggregate(events_data) # Aggregate the events
            return JsonResponse({'message': 'Aggregation completed.', 'data': new_event, 'eventsId': event_ids}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)

class RemoteIncidentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        cti_remote_topic = settings.CTI_REMOTE_TOPIC
        produce_message(cti_remote_topic, data)
        return Response({'message': 'Remote incident.'}, status=200)

class GetEventShareLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get query parameters
        organization_id = request.GET.get('organization')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Base queryset - different for superusers and normal users
        if request.user.is_staff:
            # Superusers can see all logs
            share_logs = EventShareLog.objects.select_related('event', 'event__organization', 'shared_by', 'deleted_by').all()
            # All organizations for filters
            organizations = Organization.objects.all()
        else:
            # Regular users can only see logs from their organizations
            user_organizations = request.user.organizations.all()
            if user_organizations.exists():
                share_logs = EventShareLog.objects.select_related('event', 'event__organization', 'shared_by', 'deleted_by').filter(event__organization__in=user_organizations)
                # Only their organizations for filters
                organizations = user_organizations
            else:
                return Response({'share_logs': [], 'organizations': []}, status=200)

        # Apply filters if provided
        if organization_id:
            share_logs = share_logs.filter(event__organization_id=organization_id)
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                share_logs = share_logs.filter(shared_at__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                share_logs = share_logs.filter(shared_at__lte=end_date)
            except ValueError:
                pass

        # Prepare response data
        share_logs_data = [{
            'id': log.id,
            'event_id': log.event.id,
            'event_info': log.event.data.get('info'),
            'shared_by': {
                'username': log.shared_by.username if log.shared_by else 'Unknown',
                'email': log.shared_by.email if log.shared_by else 'Unknown'
            },
            'organization': log.event.organization.name,
            'organization_id': log.event.organization.id,
            'shared_at': log.shared_at.strftime('%Y-%m-%d %H:%M:%S') if log.shared_at else None,
            'data': log.data,
            'is_unshared': True if log.deleted_at else False,
            'deleted_at': log.deleted_at.strftime('%Y-%m-%d %H:%M:%S') if log.deleted_at else None,
            'deleted_by': {
                'username': log.deleted_by.username if log.deleted_by else None,
                'email': log.deleted_by.email if log.deleted_by else None
            } if log.deleted_by else None
        } for log in share_logs]

        organizations_data = [{
            'id': org.id,
            'name': org.name
        } for org in organizations]

        return Response({
            'share_logs': share_logs_data,
            'organizations': organizations_data
        }, status=200)

class UpdateEventShareStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        event_backend = get_object_or_404(Event, id=id)
        
        if not request.user.is_staff:
            user_organizations = request.user.organizations.all()
            if not user_organizations.filter(id=event_backend.organization.id).exists():
                return Response({'error': 'Unauthorized'}, status=403)
        
        # Get the status from request data
        share_status = request.data.get('shared', False)
        
        # If the event is being unshared, mark all associated share logs as deleted
        if event_backend.shared and not share_status:
            current_time = timezone.now()
            
            share_logs = EventShareLog.objects.filter(event=event_backend)
            
            for log in share_logs:
                if log.deleted_at is None: 
                    log.deleted_by = request.user
                    log.deleted_at = current_time
                    log.save()
            
            event_backend.shared = False
            event_backend.shared_at = None
            event_backend.save()
            
            return Response({'message': 'Event unshared and share logs marked as deleted.'}, status=200)
            
        # If the event is being shared, call the share endpoint instead
        elif not event_backend.shared and share_status:
            return Response({'message': 'To share an event, use the share endpoint.'}, status=400)
        # No change needed
        else:
            return Response({'message': 'No change in share status.'}, status=200)

def new_security_alert(message, topic):
    arrival_time = timezone.now()

    # Extract organization prefix from topic
    match = re.match(r'^(UC\d+)\.', topic)
    use_case_prefix = match.group(1) if match else None
    organization = Organization.objects.get(prefix=use_case_prefix)
    
    try:
        # Parse the alert message
        alert_data = json.loads(message)
        
        parsed_alert = parse_alert_message(alert_data)
        
        # Convert date for MISP format
        timestamp = parsed_alert.get('timestamp', datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z'))
        try:
            date_obj = parser.isoparse(timestamp.replace('Z.000Z', 'Z'))  # normalize malformed variant
            formatted_date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
            unix_timestamp = str(int(date_obj.timestamp()))
        except Exception as e:
            logger.warning(f"Could not parse timestamp '{timestamp}', using current time. Error: {e}")
            formatted_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            unix_timestamp = str(int(datetime.now().timestamp()))

        # Create attributes separately
        aware_attributes = []
        risk_attributes = []
        soar_attributes = []
        
        # Add AWARE4BC attributes
        
        # Description
        description = parsed_alert.get('description', '')
        if description:
            aware_attributes.append({
                'category': 'External analysis',
                'type': 'comment',
                'value': description,
                'comment': 'Alert description',
                'to_ids': False
            })
        
        # TTP ID
        ttp_id = parsed_alert.get('ttp_id', '')
        if ttp_id:
            aware_attributes.append({
                'category': 'Attribution',
                'type': 'text',
                'value': ttp_id,
                'comment': 'MITRE ATT&CK TTP ID',
                'to_ids': False
            })
        
        # Source Asset UUID
        src_asset_uuid = parsed_alert.get('src_asset_uuid', '')
        if src_asset_uuid:
            # Check if the source IP is malicious
            from ip_reputation.models import IPReputationRecord
            
            src_comment = 'Source asset UUID'
            try:
                # First check in database
                record = IPReputationRecord.objects.filter(ip_address=src_asset_uuid).first()
                
                # If not in database, check with reputation service
                if not record:
                    from ip_reputation.services import IPReputationService
                    import asyncio
                    
                    service = IPReputationService()
                    # Run the async function synchronously
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        reputation_result = loop.run_until_complete(service.check_ip_reputation(src_asset_uuid))
                        # Re-check in database after the service call
                        record = IPReputationRecord.objects.filter(ip_address=src_asset_uuid).first()
                    finally:
                        loop.close()
                
                # Check if it's malicious
                if record and record.is_malicious:
                    src_comment = 'Source asset UUID\n/!\ MALICIOUS IP DETECTED /!\ '
            except Exception as e:
                # If any error occurs during the check, just use the basic comment
                pass
                
            aware_attributes.append({
                'category': 'Network activity',
                'type': 'ip-src',
                'value': src_asset_uuid,
                'comment': src_comment,
                'to_ids': True
            })
        
        # Destination Asset UUID
        dst_asset_uuid = parsed_alert.get('dst_asset_uuid', '')
        if dst_asset_uuid:
            # Check if the destination IP is malicious
            from ip_reputation.models import IPReputationRecord
            
            dst_comment = 'Destination asset UUID'
            try:
                # First check in database
                record = IPReputationRecord.objects.filter(ip_address=dst_asset_uuid).first()
                
                # If not in database, check with reputation service
                if not record:
                    from ip_reputation.services import IPReputationService
                    import asyncio
                    
                    service = IPReputationService()
                    # Run the async function synchronously
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        reputation_result = loop.run_until_complete(service.check_ip_reputation(dst_asset_uuid))
                        # Re-check in database after the service call
                        record = IPReputationRecord.objects.filter(ip_address=dst_asset_uuid).first()
                    finally:
                        loop.close()
                
                # Check if it's malicious
                if record and record.is_malicious:
                    dst_comment = 'Destination asset UUID\n/!\ MALICIOUS IP DETECTED /!\ '
            except Exception as e:
                # If any error occurs during the check, just use the basic comment
                pass
                
            aware_attributes.append({
                'category': 'Network activity',
                'type': 'ip-dst', 
                'value': dst_asset_uuid,
                'comment': dst_comment,
                'to_ids': True  
            })
        
        # Add all IPv4 addresses from STIX bundle format
        try:
            ipv4_addr_objects = parsed_alert.get('ipv4_addr_objects', [])
            if ipv4_addr_objects:
                from ip_reputation.models import IPReputationRecord
                
                for i, ipv4_obj in enumerate(ipv4_addr_objects):
                    # Handle both string and dict formats
                    if isinstance(ipv4_obj, dict):
                        ip_value = ipv4_obj.get('value', '')
                    elif isinstance(ipv4_obj, str):
                        ip_value = ipv4_obj
                    else:
                        continue # Skip if not a valid format

                    if ip_value and ip_value not in [src_asset_uuid, dst_asset_uuid]:  # Avoid duplicates
                        ip_comment = f'IPv4 Address #{i+1}'
                        try:
                            # First check in database
                            record = IPReputationRecord.objects.filter(ip_address=ip_value).first()
                            
                            # If not in database, check with reputation service
                            if not record:
                                from ip_reputation.services import IPReputationService
                                import asyncio
                                
                                service = IPReputationService()
                                # Run the async function synchronously
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    reputation_result = loop.run_until_complete(service.check_ip_reputation(ip_value))
                                    # Re-check in database after the service call
                                    record = IPReputationRecord.objects.filter(ip_address=ip_value).first()
                                finally:
                                    loop.close()
                            
                            # Check if it's malicious
                            if record and record.is_malicious:
                                ip_comment = f'IPv4 Address #{i+1}\n/!\ MALICIOUS IP DETECTED /!\ '
                        except Exception as e:
                            # If any error occurs during the check, just use the basic comment
                            pass
                            
                        aware_attributes.append({
                            'category': 'Network activity',
                            'type': 'ip-src',
                            'value': ip_value,
                            'comment': ip_comment,
                            'to_ids': True
                        })
        except NameError:
            # ipv4_addr_objects not defined, skip this step
            pass
        
        # Simulation information
        simulated_or_real = parsed_alert.get('simulated_or_real', '')
        if simulated_or_real:
            simulation_type = "Simulated attack" if "Simulated attack" in simulated_or_real else "Real attack"
            aware_attributes.append({
                'category': 'Other',
                'type': 'text',
                'value': simulated_or_real,
                'comment': simulation_type,
                'to_ids': False
            })
        
        # Attack UUID
        attack_uuid = parsed_alert.get('attack_uuid', '')
        if attack_uuid:
            aware_attributes.append({
                'category': 'Other',
                'type': 'text',
                'value': attack_uuid,
                'comment': 'Attack UUID',
                'to_ids': False
            })
        
        # Get complementary information from RISK4BC and SOAR4BC
        init_extension_time = datetime.now()
        
        # Configure topics
        risk_topic_temp = "RISKM4BC.riskProfile"
        risk_topic = f"{organization.prefix}.{risk_topic_temp}"
        
        soar_topic_temp = "SOAR4BC.playbook"
        soar_topic = f"{organization.prefix}.{soar_topic_temp}"
        
        # Parallel calls to consume Kafka messages
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_risk_message = executor.submit(consume_last_message, risk_topic)
            future_soar_message = executor.submit(consume_last_message, soar_topic)
            
            risk_message = future_risk_message.result()
            soar_message = future_soar_message.result()
        
        # Process RISK4BC data
        # TODO Use parse_risk_message_to_attributes function instead of manual parsing
        if risk_message is not None:
            likelihood = None
            consequence = None
            # Extract likelihood and consequence - handle both dictionary and list formats
            bowtie_values = risk_message.get('bowtieValues', [])
            if isinstance(bowtie_values, list) and len(bowtie_values) > 0:
                if isinstance(bowtie_values[0], dict):
                    # Dictionary format
                    likelihood = bowtie_values[0].get('likelihood')
                    consequence = bowtie_values[0].get('consequence')
            elif isinstance(bowtie_values, dict):
                # Handle case where bowtieValues might be a dictionary instead of a list
                for key, value in bowtie_values.items():
                    if isinstance(value, dict):
                        likelihood = value.get('likelihood')
                        consequence = value.get('consequence')
                        break
                
            # Add likelihood and consequence to event data
            if likelihood is not None and consequence is not None:
                risk_attributes.append({
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
                    risk_attributes.append({
                        'type': 'text',
                        'category': 'Other',
                        'value': f'Cascade effect: {cascade}',
                        'comment': 'Cascade information',
                        'to_ids': False
                    })
            elif isinstance(cascades, dict):
                for key, cascade in cascades.items():
                    risk_attributes.append({
                        'type': 'text',
                        'category': 'Other',
                        'value': f'Cascade effect: {cascade}',
                        'comment': 'Cascade information',
                        'to_ids': False
                    })
        
        # Process SOAR4BC data
        if soar_message is not None:
            soar_attributes = preprocess_soar_message_into_attributes(soar_message)
        
        # Calculate total number of attributes
        total_attributes = len(aware_attributes) + len(risk_attributes) + len(soar_attributes)
        
        # Create strict MISP format data (without Attribute field in the main structure)
        misp_format_data = {
            'org_id': str(organization.external_id),
            'distribution': '0',  # Default: Your organization only
            'info': parsed_alert.get('attack_name', 'No information available'),
            'orgc_id': str(organization.external_id),
            'date': formatted_date,
            'published': False,
            'analysis': '0',  # Default: Initial
            'attribute_count': str(total_attributes),
            'timestamp': unix_timestamp,
            'sharing_group_id': '1',
            'proposal_email_lock': False,
            'locked': True,
            'threat_level_id': '1',  # Default: High
            'publish_timestamp': unix_timestamp,
            'sighting_timestamp': unix_timestamp,
            'disable_correlation': False,
            'event_creator_email': organization.email
        }
        
        # Store attributes separately in our internal structure
        # This keeps the misp_format_data clean while still allowing us to work with attributes
        internal_data = misp_format_data.copy()
        internal_data['Attribute'] = {
            'AWARE4BC': aware_attributes,
            'RISK4BC': risk_attributes,
            'SOAR4BC': soar_attributes
        }
        
        finish_extension_time = datetime.now()
        extension_time = finish_extension_time - init_extension_time
        
        # Create and save the event with our internal data format
        event = Event(data=internal_data, shared=False, organization=organization, arrival_time=arrival_time, extension_time=extension_time)
        event.save()
        return Response({'message': 'New event created with MMT alert data.'}, status=201)
    
    except Exception as e:
        # In case of error, return an error response
        logger.error(f"Error processing new security alert: {e}", exc_info=True)
        return Response({'error': f'Failed to process alert: {str(e)}'}, status=400)
    
class UpdateRiskProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        """
        Retrieves the latest risk profile for the organization associated with the event and updates the event's data.
        """
        event = get_object_or_404(Event, id=id)

        # Authorization check
        if not request.user.is_staff:
            user_organizations = request.user.organizations.all()
            if not user_organizations.filter(id=event.organization.id).exists():
                return Response({'error': 'Unauthorized'}, status=403)
        
        org = event.organization
        topic = f"{org.prefix}.RISKM4BC.riskProfile"

        try:
            risk_message = consume_last_message(topic)
            if risk_message is None:
                return Response(status=204)
            else:
                risk_attributes = parse_risk_message_to_attributes(risk_message)
                event.data['Attribute']['RISK4BC'] = risk_attributes
                event.save()
                return Response({'Attribute': {'RISK4BC': risk_attributes}}, status=200)
        except Exception as e:
            return Response({"error": f"Failed to fetch RISK4BC: {str(e)}"}, status=500)

class UpdatePlaybookView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        """
        Retrieves the latest SOAR4BC playbook data for the event
        updates the event's data with new SOAR4BC attributes.
        """

        event = get_object_or_404(Event, id=id)

        # Authorization check
        if not request.user.is_staff:
            user_organizations = request.user.organizations.all()
            if not user_organizations.filter(id=event.organization.id).exists():
                return Response({'error': 'Unauthorized'}, status=403)
        
        org = event.organization
        topic = f"{org.prefix}.SOAR4BC.playbook"

        try:
            soar_message = consume_last_message(topic)
            if soar_message is None:
                return Response(status=204)
            else:
                soar_attributes = preprocess_soar_message_into_attributes(soar_message)
                event.data['Attribute']['SOAR4BC'] = soar_attributes
                event.save()
                return Response({'Attribute': {'SOAR4BC': soar_attributes}}, status=200)
        except Exception as e:
            return Response({"error": f"Failed to fetch SOAR4BC: {str(e)}"}, status=500)