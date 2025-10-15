from django.apps import AppConfig


class IpReputationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ip_reputation'
    verbose_name = "IP Reputation Service"
    
    def ready(self):
        # Import dashboard module to register admin customizations
        import ip_reputation.dashboard
        # Import signals
        import ip_reputation.signals
