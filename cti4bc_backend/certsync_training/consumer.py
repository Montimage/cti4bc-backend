"""One shared consumer, subscribing to all organisations before any run sends."""
import threading
import time
from django.conf import settings

_lock = threading.Lock()


def all_topics():
    from organizations.models import Organization
    prefixes = Organization.objects.values_list("prefix", flat=True)
    return sorted({f"{prefix}.HEALTHCI.security_alerts" for prefix in prefixes})


def ensure_consumer(timeout=30):
    from cti4bc_backend import kafka_views
    from cti4bc.kafkaConsumer import KafkaConsumerThread
    topics = all_topics()
    with _lock:
        manager = kafka_views.consumer_manager
        if manager is not None and set(manager.topics) != set(topics):
            # Never replace a consumer under other participants' running chains.
            return False, topics
        if manager is None or not manager.thread or not manager.thread.is_alive():
            manager = KafkaConsumerThread(topics, settings.KAFKA_SERVER,
                settings.KAFKA_USERNAME, settings.KAFKA_PASSWORD,
                {topic: kafka_views.message_handler_with_history for topic in topics})
            kafka_views.consumer_manager = manager
            manager.start()
    deadline = time.monotonic() + timeout
    while True:
        if manager.ready_event.is_set() and set(topics).issubset(manager.assigned_topics):
            return True, topics
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False, topics
        time.sleep(min(0.1, remaining))
