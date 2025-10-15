from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
import json
from collections import defaultdict

from .models import Form, FormAnswer
from .serializers import FormSerializer, FormAnswerSerializer, FormListSerializer
from event.models import Event
from .google_forms_service import GoogleFormsService


class FormListCreateView(APIView):
    """
    API View to list all forms for user's organization or create a new form
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get all forms for the user's organizations
        """
        if request.user.is_staff:
            # Superusers can see all forms
            forms = Form.objects.all()
        else:
            # Regular users can only see forms from their organizations
            user_organizations = request.user.organizations.all()
            if user_organizations.exists():
                forms = Form.objects.filter(organizations__in=user_organizations).distinct()
            else:
                forms = Form.objects.none()

        # Filter by active status if requested
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            forms = forms.filter(is_active=is_active.lower() == 'true')

        serializer = FormListSerializer(forms, many=True)
        return Response({'forms': serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a new form
        """
        serializer = FormSerializer(data=request.data)
        if serializer.is_valid():
            # Validate organization permissions
            organization_ids = serializer.validated_data.get('organizations', [])
            if not request.user.is_staff and organization_ids:
                user_organizations = request.user.organizations.all()
                user_org_ids = set(user_organizations.values_list('id', flat=True))
                requested_org_ids = set(org.id for org in organization_ids)
                
                if not requested_org_ids.issubset(user_org_ids):
                    return Response(
                        {'error': 'You can only create forms for your organizations'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            saved_form = serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FormDetailView(APIView):
    """
    API View to retrieve, update or delete a specific form
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        """
        Get form instance with permission checking
        """
        if user.is_staff:
            return get_object_or_404(Form, pk=pk)
        else:
            user_organizations = user.organizations.all()
            return get_object_or_404(Form, pk=pk, organizations__in=user_organizations)

    def get(self, request, pk):
        """
        Retrieve a specific form
        """
        form = self.get_object(pk, request.user)
        serializer = FormSerializer(form)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        """
        Update a specific form
        """
        form = self.get_object(pk, request.user)
        serializer = FormSerializer(form, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        """
        Partially update a specific form
        """
        form = self.get_object(pk, request.user)
        serializer = FormSerializer(form, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """
        Delete a specific form
        """
        form = self.get_object(pk, request.user)
        form.delete()
        return Response({'message': 'Form deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


class FormAnswerListCreateView(APIView):
    """
    API View to list form answers or create a new answer
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get form answers - can be filtered by form_id or event_id
        """
        form_id = request.query_params.get('form_id')
        event_id = request.query_params.get('event_id')
        filled_by_current_user = request.query_params.get('filled_by_current_user', '').lower() == 'true'
        
        try:
            if filled_by_current_user:
                # Special case: user wants to see only their own answers
                answers = FormAnswer.objects.filter(filled_by=request.user)
            elif request.user.is_staff:
                answers = FormAnswer.objects.all()
            else:
                # For checking user's own answers, we should filter by the current user
                # This is especially important when checking what forms a user has already filled
                if event_id:
                    # When checking for a specific event, show only current user's answers
                    answers = FormAnswer.objects.filter(filled_by=request.user)
                else:
                    # For general listing, use organization filtering
                    user_organizations = request.user.organizations.all()
                    answers = FormAnswer.objects.filter(
                        Q(form__organizations__in=user_organizations) |
                        Q(event__organization__in=user_organizations)
                    )

            if form_id:
                answers = answers.filter(form_id=form_id)
            if event_id:
                answers = answers.filter(event_id=event_id)

            serializer = FormAnswerSerializer(answers, many=True)
            return Response({'answers': serializer.data}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': 'Failed to fetch form answers', 
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """
        Create a new form answer
        """
        serializer = FormAnswerSerializer(data=request.data)
        if serializer.is_valid():
            # Verify user has access to the form and event
            form_id = serializer.validated_data['form'].id
            event_id = serializer.validated_data['event'].id
            
            if not request.user.is_staff:
                user_organizations = request.user.organizations.all()
                
                # Check form access
                if not Form.objects.filter(id=form_id, organizations__in=user_organizations).exists():
                    return Response(
                        {'error': 'You do not have access to this form'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Check event access
                if not Event.objects.filter(id=event_id, organization__in=user_organizations).exists():
                    return Response(
                        {'error': 'You do not have access to this event'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # Get client IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            serializer.save(filled_by=request.user, ip_address=ip)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FormAnswerDetailView(APIView):
    """
    API View to retrieve, update or delete a specific form answer
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        """
        Get form answer instance with permission checking
        """
        if user.is_staff:
            return get_object_or_404(FormAnswer, pk=pk)
        else:
            # Users can access their own answers or answers from their organizations
            return get_object_or_404(
                FormAnswer, 
                pk=pk, 
                filled_by=user
            )

    def get(self, request, pk):
        """
        Retrieve a specific form answer
        """
        answer = self.get_object(pk, request.user)
        serializer = FormAnswerSerializer(answer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        """
        Update a specific form answer (only if user filled it)
        """
        answer = self.get_object(pk, request.user)
        
        # Only allow users to edit their own answers (or staff)
        if not request.user.is_staff and answer.filled_by != request.user:
            return Response(
                {'error': 'You can only edit your own form answers'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = FormAnswerSerializer(answer, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """
        Delete a specific form answer (only if user filled it or is staff)
        """
        answer = self.get_object(pk, request.user)
        
        # Only allow users to delete their own answers (or staff)
        if not request.user.is_staff and answer.filled_by != request.user:
            return Response(
                {'error': 'You can only delete your own form answers'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        answer.delete()
        return Response({'message': 'Form answer deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


class EventFormsView(APIView):
    """
    API View to get available forms for a specific event (based on event's organization)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        """
        Get all active forms available for a specific event
        """
        # Get the event
        if request.user.is_staff:
            event = get_object_or_404(Event, pk=event_id)
        else:
            user_organizations = request.user.organizations.all()
            event = get_object_or_404(Event, pk=event_id, organization__in=user_organizations)
        
        # Get active forms for the event's organization
        forms = Form.objects.filter(
            organization=event.organization,
            is_active=True
        )
        
        serializer = FormListSerializer(forms, many=True)
        return Response({
            'event_id': event_id,
            'event_info': event.data.get('info', 'No info available'),
            'forms': serializer.data
        }, status=status.HTTP_200_OK)


class GoogleFormImportView(APIView):
    """
    API View to import Google Forms via Apps Script API URL only
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Import a Google Form by URL via Google Apps Script
        """
        try:
            form_url = request.data.get('form_url')
            
            if not form_url:
                return Response({
                    'error': 'form_url is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            raw_form_json = None
            
            # Import by URL via Google Apps Script
            try:
                raw_form_json = GoogleFormsService.import_from_url(form_url)
            except Exception as e:
                error_msg = str(e).lower()
                
                # Provide more specific error messages based on the error content
                if 'élément introuvable' in error_msg or 'not found' in error_msg or '404' in error_msg:
                    return Response({
                        'error': 'Google Form not found. Please check that: 1) The URL is correct, 2) The form exists, 3) The form is accessible to the account running the script.'
                    }, status=status.HTTP_404_NOT_FOUND)
                elif 'autorisé' in error_msg or 'permission' in error_msg or 'access' in error_msg or '403' in error_msg:
                    return Response({
                        'error': 'Access denied to the Google Form. The form may be private or you may not have the necessary permissions to access it.'
                    }, status=status.HTTP_403_FORBIDDEN)
                elif 'invalid' in error_msg and 'url' in error_msg:
                    return Response({
                        'error': 'Invalid Google Forms URL format. Please provide a valid Google Forms URL (e.g., https://docs.google.com/forms/d/FORM_ID/edit)'
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({
                        'error': f'Failed to import form from URL: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Transform the Apps Script JSON to internal form format
            try:
                form_creation_data = GoogleFormsService.get_form_creation_data(raw_form_json)
                
                # Add organizations from request if provided
                if 'organizations' in request.data:
                    form_creation_data['organizations'] = request.data['organizations']
                
                # Validate with FormSerializer
                serializer = FormSerializer(data=form_creation_data)
                if serializer.is_valid():
                    # Validate organization permissions
                    organization_ids = serializer.validated_data.get('organizations', [])
                    if not request.user.is_staff and organization_ids:
                        user_organizations = request.user.organizations.all()
                        user_org_ids = set(user_organizations.values_list('id', flat=True))
                        requested_org_ids = set(org.id for org in organization_ids)
                        
                        if not requested_org_ids.issubset(user_org_ids):
                            return Response(
                                {'error': 'You can only create forms for your organizations'}, 
                                status=status.HTTP_403_FORBIDDEN
                            )
                    
                    # Save the form
                    saved_form = serializer.save(created_by=request.user)
                    
                    return Response({
                        'message': 'Form imported successfully',
                        'form': FormSerializer(saved_form).data
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response({
                        'error': 'Form validation failed',
                        'details': serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                return Response({
                    'error': f'Failed to transform form data: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({
                'error': f'Unexpected error during form import: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class FormStatsView(APIView):
    """
    API View to get statistics and KPIs for forms
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, form_id=None):
        """
        Get statistics for a specific form or all forms
        """
        try:
            if form_id:
                # Get stats for a specific form
                if request.user.is_staff:
                    form = get_object_or_404(Form, pk=form_id)
                else:
                    user_organizations = request.user.organizations.all()
                    form = get_object_or_404(Form, pk=form_id, organizations__in=user_organizations)
                
                stats = self._calculate_form_stats(form)
                return Response({
                    'form_id': form_id,
                    'form_title': form.title,
                    'stats': stats
                }, status=status.HTTP_200_OK)
            else:
                # Get overview stats for all forms
                if request.user.is_staff:
                    forms = Form.objects.all()
                else:
                    user_organizations = request.user.organizations.all()
                    forms = Form.objects.filter(organizations__in=user_organizations).distinct()
                
                overview_stats = self._calculate_overview_stats(forms)
                return Response({
                    'overview_stats': overview_stats
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response({
                'error': f'Failed to fetch form statistics: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _calculate_form_stats(self, form):
        """
        Calculate detailed statistics for a specific form
        """
        answers = FormAnswer.objects.filter(form=form)
        total_responses = answers.count()
        
        if total_responses == 0:
            return {
                'total_responses': 0,
                'field_stats': {},
                'response_rate': 0,
                'completion_trends': []
            }
        
        # Analyze each field in the form
        field_stats = {}
        form_fields = form.fields if isinstance(form.fields, list) else []
        
        for field in form_fields:
            field_name = field.get('name', '')
            field_type = field.get('type', '')
            field_label = field.get('label', field_name)
            field_options = field.get('options', [])
            
            # Skip if not a choice-based question
            if field_type not in ['radio', 'checkbox', 'select']:
                continue
                
            # Count responses for this field
            field_responses = []
            for answer in answers:
                if field_name in answer.answers:
                    response_value = answer.answers[field_name]
                    if isinstance(response_value, list):
                        field_responses.extend(response_value)
                    else:
                        field_responses.append(response_value)
            
            if field_responses:
                # Calculate statistics for choice fields
                choice_counts = defaultdict(int)
                for response in field_responses:
                    if response:  # Skip empty responses
                        choice_counts[str(response)] += 1
                
                # Calculate percentages
                total_field_responses = len(field_responses)
                choice_percentages = {}
                for choice, count in choice_counts.items():
                    choice_percentages[choice] = {
                        'count': count,
                        'percentage': round((count / total_field_responses) * 100, 1)
                    }
                
                field_stats[field_name] = {
                    'label': field_label,
                    'type': field_type,
                    'total_responses': total_field_responses,
                    'response_rate': round((total_field_responses / total_responses) * 100, 1),
                    'choice_distribution': choice_percentages,
                    'available_options': field_options
                }
        
        # Calculate completion trends (by day)
        completion_trends = self._calculate_completion_trends(answers)
        
        return {
            'total_responses': total_responses,
            'field_stats': field_stats,
            'completion_trends': completion_trends,
            'response_rate': 100  # Assuming all who started, completed
        }

    def _calculate_overview_stats(self, forms):
        """
        Calculate overview statistics for all forms
        """
        total_forms = forms.count()
        total_responses = FormAnswer.objects.filter(form__in=forms).count()
        
        # Forms with most responses
        popular_forms = []
        for form in forms[:10]:  # Top 10
            response_count = FormAnswer.objects.filter(form=form).count()
            if response_count > 0:
                popular_forms.append({
                    'id': form.id,
                    'title': form.title,
                    'response_count': response_count
                })
        
        # Sort by response count
        popular_forms.sort(key=lambda x: x['response_count'], reverse=True)
        
        # Response trends over time
        response_trends = self._calculate_overall_response_trends(forms)
        
        return {
            'total_forms': total_forms,
            'total_responses': total_responses,
            'average_responses_per_form': round(total_responses / total_forms, 1) if total_forms > 0 else 0,
            'popular_forms': popular_forms[:5],  # Top 5
            'response_trends': response_trends
        }

    def _calculate_completion_trends(self, answers):
        """
        Calculate when responses were submitted (daily trends)
        """
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        # Get responses from last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_answers = answers.filter(filled_at__gte=thirty_days_ago)
        
        daily_counts = defaultdict(int)
        for answer in recent_answers:
            date_str = answer.filled_at.strftime('%Y-%m-%d')
            daily_counts[date_str] += 1
        
        # Convert to list format for charts
        trends = []
        for i in range(30):
            date = (timezone.now() - timedelta(days=29-i)).strftime('%Y-%m-%d')
            trends.append({
                'date': date,
                'count': daily_counts.get(date, 0)
            })
        
        return trends

    def _calculate_overall_response_trends(self, forms):
        """
        Calculate overall response trends across all forms
        """
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        # Get all responses from last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        all_answers = FormAnswer.objects.filter(
            form__in=forms,
            filled_at__gte=thirty_days_ago
        )
        
        daily_counts = defaultdict(int)
        for answer in all_answers:
            date_str = answer.filled_at.strftime('%Y-%m-%d')
            daily_counts[date_str] += 1
        
        # Convert to list format
        trends = []
        for i in range(30):
            date = (timezone.now() - timedelta(days=29-i)).strftime('%Y-%m-%d')
            trends.append({
                'date': date,
                'count': daily_counts.get(date, 0)
            })
        
        return trends
