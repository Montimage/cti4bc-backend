from django.shortcuts import render
from .forms import PlaybookForm
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Playbook
from .serializers import PlaybookSerializer
from event.models import Event
from rest_framework.permissions import IsAuthenticated
import re

def preprocess_soar_message_into_attributes(data):
    """
    Parses the SOAR4BC message of a cacao v2 playbook into MISP attributes.
    Args:
        data (dict): The SOAR4BC message including a 'workflow' key.
    Returns:
        list: A list of MISP attributes.
    """
    attributes = []
    workflow = data.get('workflow', [])
    for node_id, node in workflow.items():
        attribute = {
            'type': 'text',
            'category': 'Internal reference',
            'value': f"Node ID: {node_id}, Name: {node.get('name', 'Unknown')}, Type: {node.get('type', 'Unknown')}",
            'comment': f"Workflow step details: {node.get('description', 'No description available')}",
            'to_ids': False
        }

        # Add additional relationships for actions
        if node.get('type') == 'action':
            commands = ", ".join(
                cmd.get("type", "unknown") for cmd in node.get("commands", [])
            )
            agent = node.get("agent", "unknown agent")
            attribute["value"] += f", Commands: {commands}, Agent: {agent}"
        
        # Add the next step, if present
        if "on_completion" in node:
            attribute["comment"] += f" Next step: {node['on_completion']}"

        attributes.append(attribute)
     
    return attributes

class PlaybokCreateUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        external_id = request.data.get('_id')
        if not external_id:
            return Response({"message": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST)
        processed_data = preprocess_soar_message_into_attributes(request.data)

        playbook, created = Playbook.objects.get_or_create(external_id=external_id)
        playbook.data = processed_data

        if not playbook.event:
            try:
                event = Event.objects.get(external_id=external_id)
                playbook.event = event
            except Event.DoesNotExist:
                pass
        playbook.save()
        message = "Playbook created" if created else "Playbook updated"
        return Response({"message": message}, status=status.HTTP_200_OK)

class PlaybookByEventView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        playbooks = Playbook.objects.filter(event=id)
        playbook_data_list = [playbook.data for playbook in playbooks]
        response_data = {
            "playbooks": playbook_data_list
        }
        return Response(response_data, status=status.HTTP_200_OK)

@csrf_exempt # This decorator is used to exempt the view from CSRF verification TODO Delete in production
def get_by_event(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            event_id = body.get('event_id', None)
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON"}, status=400)

        if event_id is None:
            return JsonResponse({"message": "Invalid data"}, status=400)
        try:
            playbooks = Playbook.objects.filter(event=event_id)
            data = []
            for playbook in playbooks:
                data.append(playbook.data)
            response_data = {
                "playbooks": data
            }
            return JsonResponse(response_data, status=200, safe=False)
        except Playbook.DoesNotExist:
            return JsonResponse({"playbooks": []}, status=200)
    else:
        return JsonResponse({"message": "Invalid request method"}, status=405)

def new_playbook(message, topic):
    """
    Function to receive and process SOAR4BC messages, parse them into MISP attributes and save them as playbooks for the corresponding topic.
    """
    json_message = json.loads(message)
    
    # Get external id from the message
    playbook_id = json_message.get('id')
    match = re.match(r"playbook--(.+)", playbook_id)
    event_external_id = match.group(1) if match else None

    playbook_data = preprocess_soar_message_into_attributes(json_message)

    playbook, created = Playbook.objects.get_or_create(external_id=playbook_id)
    playbook.data = playbook_data

    # Check if the event exists and assign it to the playbook
    if not playbook.event:
        try:
            event = Event.objects.get(external_id=event_external_id)
            playbook.event = event
        except Event.DoesNotExist:
            pass
    playbook.save()
    return Response({"message": message}, status=status.HTTP_200_OK)

