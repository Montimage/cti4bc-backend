from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Strategy
from .serializers import StrategyListSerializer, StrategyDetailSerializer, AddStrategySerializer

class StrategyListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            strategies = Strategy.objects.all()
        else:
            user_orgs = request.user.organizations.all()
            strategies = Strategy.objects.filter(organizations__in=user_orgs).distinct()
        serializer = StrategyListSerializer(strategies, many=True)
        data = {
            'strategies': serializer.data
        }
        return Response(data, status=status.HTTP_200_OK)

class StrategyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        if request.user.is_staff:
            strategy = get_object_or_404(Strategy, id=id)
        else:
            user_orgs = request.user.organizations.all()
            strategy = get_object_or_404(Strategy, id=id, organizations__in=user_orgs)
        serializer = StrategyDetailSerializer(strategy)
        data = {
            'strategy': serializer.data
        }
        return Response(data, status=status.HTTP_200_OK)

class AddStrategyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AddStrategySerializer(data=request.data)
        if serializer.is_valid():
            strategy = serializer.save()

            # Get orgs of the user
            user_orgs = request.user.organizations.all()

            if user_orgs.exists(): # Add the strategy to the user's organizations   
                strategy.organizations.set(user_orgs)
                
            return Response({'message': 'Strategy added successfully'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DeleteStrategyView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, id):
        if not request.user.is_staff:
            return Response({'error': 'Only staff users can delete strategies.'}, status=status.HTTP_403_FORBIDDEN)
        strategy = get_object_or_404(Strategy, id=id)
        strategy.delete()
        return Response({'message': 'Strategy deleted successfully'}, status=status.HTTP_204_NO_CONTENT)