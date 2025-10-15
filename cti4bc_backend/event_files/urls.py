from django.urls import path
from .views import EventFileUploadView, DeleteEventAttachmentView, DownloadEventAttachmentView

urlpatterns = [
    path('upload/', EventFileUploadView.as_view(), name='event-attachment-upload'),
    path('delete/<int:attachment_id>/', DeleteEventAttachmentView.as_view(), name='event-attachment-delete'),
    path('download/<int:attachment_id>/', DownloadEventAttachmentView.as_view(), name='event-attachment-download'),
]