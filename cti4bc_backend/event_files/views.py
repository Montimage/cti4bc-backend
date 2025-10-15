from rest_framework import status
from .serializers import EventAttachmentSerializer
from rest_framework.permissions import IsAuthenticated
from event.models import Event
from rest_framework.response import Response
from rest_framework.views import APIView
import os
from .models import EventAttachment
from django.conf import settings
from django.http import FileResponse

import logging

logger = logging.getLogger(__name__)

class EventFileUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        event_id = request.data.get('event')

        logger.info(f"User {user.username} ({user.id}) attempting to upload file(s) for event {event_id}")
        try:
            event = Event.objects.get(id=event_id)
            logger.info(f"Event found")
        except Event.DoesNotExist:
            logger.warning(f"Event not found: {event_id}")
            return Response({'error': 'Event not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if the user is part of the event's organization
        if not event.organization.users.filter(id=user.id).exists():
            logger.warning(f"User {user.username} ({user.id}) not authorized for event {event_id}")
            return Response({'error': 'User not authorized to upload attachments for this event'}, status=status.HTTP_403_FORBIDDEN)
        
        files = request.FILES.getlist('file')
        if not files:
            return Response({'error': 'No files uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        for file in files:
            serializer = EventAttachmentSerializer(data={"file": file, "event": event_id})
            if serializer.is_valid():
                serializer.save(uploaded_by=user, event=event)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            updated_files = EventAttachment.objects.filter(event=event_id).values(
                'id', 'file', 'uploaded_at', 'uploaded_by__username'
            )

            formatted_files = [
            {
                'id': attachment['id'],
                'file': os.path.basename(attachment['file']),  # Extract only the filename
                'uploaded_at': attachment['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S'),  # Format timestamp
                'uploaded_by': attachment['uploaded_by__username']
            }
            for attachment in updated_files
            ]
        return Response({"message": "Files uploaded successfully", "files": formatted_files}, status=status.HTTP_201_CREATED)

class DeleteEventAttachmentView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, attachment_id, *args, **kwargs):
        try:
            attachment = EventAttachment.objects.get(id=attachment_id)
        except EventAttachment.DoesNotExist:
            return Response({'error': 'Attachment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        user = request.user
        event = attachment.event

        # Check if the user is part of the event's organization
        if not event.organization.users.filter(id=user.id).exists():
            return Response({'error': 'User not authorized to delete attachments for this event'}, status=status.HTTP_403_FORBIDDEN)
        
        file_path = os.path.join(settings.MEDIA_ROOT, str(attachment.file))
        if os.path.exists(file_path):
            os.remove(file_path)
        
        attachment.delete()

        updated_files = EventAttachment.objects.filter(event=event).values(
                'id', 'file', 'uploaded_at', 'uploaded_by__username'
            )

        formatted_files = [
        {
            'id': attachment['id'],
            'file': os.path.basename(attachment['file']),  # Extract only the filename
            'uploaded_at': attachment['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S'),  # Format timestamp
            'uploaded_by': attachment['uploaded_by__username']
        }
        for attachment in updated_files
        ]
        return Response({'message': 'Attachment deleted successfully','files': formatted_files }, status=status.HTTP_200_OK)
    
class DownloadEventAttachmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attachment_id, *args, **kargs):
        try:
            attachment = EventAttachment.objects.get(id=attachment_id)
        except EventAttachment.DoesNotExist:
            return Response({'error': 'Attachment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        user = request.user
        event = attachment.event

        # Check if the user is part of the event's organization
        has_access = (
            attachment.public or
            event.organization.users.filter(id=user.id).exists()
        )
        if not has_access:
            return Response({'error': 'User not authorized to download this attachment'}, status=status.HTTP_403_FORBIDDEN)
        
        # Construct the file path
        file_path = os.path.join(settings.MEDIA_ROOT, str(attachment.file))

        # Check if the file exists
        if not os.path.exists(file_path):
            return Response({'error': 'Attachment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        filename = os.path.basename(file_path)

        # Serve the file as a download
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response