from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import uuid
import logging

logger = logging.getLogger(__name__)

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom token view that inherits from the default TokenObtainPairView.
    The last_login will be updated when user info is accessed.
    """
    pass

class UserRegistrationView(APIView):
    """
    API view for user registration.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return Response({'detail': 'User with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate a random username if email doesn't exist as username
        username = email.split('@')[0]
        if User.objects.filter(username=username).exists():
            username = f"{username}_{uuid.uuid4().hex[:8]}"
            
        # Generate a random password
        password = uuid.uuid4().hex[:10]
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_active=True  # Set to False if you want email verification
            )
            
            # Send email with credentials (optional but recommended)
            try:
                send_mail(
                    'Your CTI4BC Account Information',
                    f'Your account has been created.\n\nUsername: {username}\nPassword: {password}\n\nPlease login and change your password.',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send email: {str(e)}")
                # Consider whether to delete the user if email fails
                # For now, we'll continue but log the error
            
            # Return the credentials to the frontend
            return Response({
                'detail': 'User registered successfully.',
                'email': email,
                'username': username,
                'password': password
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return Response({
                'detail': 'Registration failed. Please try again later.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        organizations = user.organizations.all()
        
        # Update last_login when user info is accessed
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'is_active': user.is_active,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'organizations': [
                {
                    'id': org.id,
                    'name': org.name,
                    'prefix': org.prefix
                }
                for org in organizations
            ]
        })

class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        data = request.data
        
        try:
            # Update user fields
            if 'username' in data:
                # Check if username is already taken by another user
                if User.objects.filter(username=data['username']).exclude(id=user.id).exists():
                    return Response({'detail': 'Username already taken'}, status=status.HTTP_400_BAD_REQUEST)
                user.username = data['username']
            
            if 'email' in data:
                # Check if email is already taken by another user
                if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
                    return Response({'detail': 'Email already taken'}, status=status.HTTP_400_BAD_REQUEST)
                user.email = data['email']
            
            if 'first_name' in data:
                user.first_name = data['first_name']
            
            if 'last_name' in data:
                user.last_name = data['last_name']
            
            user.save()
            
            # Return updated user info
            organizations = user.organizations.all()
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'is_active': user.is_active,
                'date_joined': user.date_joined.isoformat() if user.date_joined else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'organizations': [
                    {
                        'id': org.id,
                        'name': org.name,
                        'prefix': org.prefix
                    }
                    for org in organizations
                ]
            })
            
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            return Response({'detail': 'Failed to update profile'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return Response({'detail': 'Current password and new password are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check current password
        if not user.check_password(current_password):
            return Response({'detail': 'Current password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate new password length
        if len(new_password) < 8:
            return Response({'detail': 'New password must be at least 8 characters long'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Set new password
            user.set_password(new_password)
            user.save()
            
            return Response({'detail': 'Password changed successfully'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error changing password: {str(e)}")
            return Response({'detail': 'Failed to change password'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)