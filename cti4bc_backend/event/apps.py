from django.apps import AppConfig

class EventConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'event'
    
    def ready(self):
        """
        Method called when the Django application is ready.
        Imports signals to register them automatically.
        """
        import event.signals  # Import the signals module to register signals
