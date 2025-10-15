from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from cti4bc.kafkaConsumer import KafkaConsumerThread
from django.conf import settings
from event.views import new_security_alert
import json
import threading
from collections import deque

# Global variables for message storage
consumer_manager = None
message_history = deque(maxlen=100)  # Store last 100 messages
message_lock = threading.Lock()

# Custom handler that saves messages to history
def message_handler_with_history(message, topic):
    # Process the message with the regular handler (for security alerts)
    try:
        new_security_alert(message, topic)
    except Exception as e:
        print(f"Error in new_security_alert: {e}")
    
    # Also save to our history for UI display
    try:
        # Ensure message is a string before parsing
        if not isinstance(message, str):
            message = str(message)
            
        # Try to parse the message as JSON
        try:
            parsed_message = json.loads(message)
            
            # Store in history with parsed JSON
            with message_lock:
                message_entry = {
                    'topic': topic,
                    'timestamp': parsed_message.get('timestamp', ''),
                    'message': parsed_message
                }
                message_history.appendleft(message_entry)
        except json.JSONDecodeError as e:
            # Store as raw string if parsing fails
            with message_lock:
                message_entry = {
                    'topic': topic,
                    'timestamp': '',
                    'value': message  # Use 'value' for raw messages
                }
                message_history.appendleft(message_entry)
    except Exception as e:
        print(f"Error processing message for history: {e}")
        # Last resort fallback
        try:
            with message_lock:
                message_entry = {
                    'topic': topic,
                    'timestamp': '',
                    'value': str(message)  # Ensure it's a string
                }
                message_history.appendleft(message_entry)
        except Exception as e2:
            print(f"Critical error storing message: {e2}")

class StartConsumerView(APIView):
    """
    API View to start the Kafka consumer.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        global consumer_manager, message_history
        topics = request.data.get('topics', [])
        if not topics:
            return Response({'error': 'No topics provided.'}, status=400)
        
        # Make sure topics is a list
        if isinstance(topics, str):
            topics = [topics]
            
        if consumer_manager is None:
            # Clear message history when starting a new consumer
            with message_lock:
                message_history.clear()
            
            # Register handler for each topic
            topic_handlers = {}
            for topic in topics:
                topic_handlers[topic] = message_handler_with_history
            
            consumer_manager = KafkaConsumerThread(
                topics=topics,
                kafka_url=settings.KAFKA_SERVER,
                kafka_username=settings.KAFKA_USERNAME,
                kafka_password=settings.KAFKA_PASSWORD,
                handlers=topic_handlers
            )
            consumer_manager.start()
            
        return Response({'status': 'Consumer started.', 'topics': topics}, status=200)

class StopConsumerView(APIView):
    """
    API View to stop the Kafka consumer.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        global consumer_manager, message_history
        
        if consumer_manager is not None:
            try:
                consumer_manager.stop()
                consumer_manager = None
                
                # Clear message history when stopping consumer
                with message_lock:
                    message_history.clear()
                    
                return Response({'status': 'Consumer stopped.'}, status=200)
            except Exception as e:
                return Response({'status': f'Error stopping consumer: {str(e)}'}, status=500)
        else:
            return Response({'status': 'No consumer was running.'}, status=200)

class EnvVariablesView(APIView):
    """
    API View to display environment variables from .env file.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Display all environment variables
        env_vars = {}
        
        # Get specific environment variables
        env_vars = {
            'KAFKA_SERVER': settings.KAFKA_SERVER,
            'KAFKA_USERNAME': settings.KAFKA_USERNAME,
            'KAFKA_PASSWORD': '*****' if settings.KAFKA_PASSWORD else 'Not set',
            # Add other variables as needed
        }
        
        # Try to retrieve other common Django variables
        for var in ['DEBUG', 'SECRET_KEY', 'DATABASE_URL', 'ALLOWED_HOSTS']:
            if hasattr(settings, var):
                env_vars[var] = str(getattr(settings, var))
        
        return Response({'env_variables': env_vars})

class GetConsumerStatusView(APIView):
    """
    API View to check the status of the Kafka consumer.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        global consumer_manager
        status = 'running' if consumer_manager and consumer_manager.thread and consumer_manager.thread.is_alive() else 'stopped'
        topics = consumer_manager.topics if consumer_manager else []
        
        return Response({
            'status': status,
            'topics': topics,
            'kafka_server': settings.KAFKA_SERVER,
            'kafka_username': settings.KAFKA_USERNAME
        }, status=200)

class GetKafkaMessagesView(APIView):
    """
    API View to retrieve the last Kafka messages.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        global message_history
        
        with message_lock:
            # Convert deque to list for JSON serialization
            messages = list(message_history)
            
        # Return the messages
        response_data = {'messages': messages}
        
        return Response(response_data, status=200)