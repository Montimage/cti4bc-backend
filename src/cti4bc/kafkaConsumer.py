import logging
from threading import Thread, Event
from kafka import KafkaConsumer, TopicPartition

class KafkaConsumerThread:
    def __init__(self, topics, kafka_url, kafka_username, kafka_password, handlers):
        """
        Initialize the KafkaConsumerThread class.
        Args:
            topics (list): List of topics to subscribe to.
            kafka_url (str): Kafka broker URL.
            kafka_username (str): SASL username.
            kafka_password (str): SASL password.
            handlers (dict): Dictionary mapping topics to handler methods. Handler will be called with message and topic as args.
        """
        self.topics = topics
        self.kafka_url = kafka_url
        self.kafka_username = kafka_username
        self.kafka_password = kafka_password
        self.handlers = handlers
        self.thread = None
        self.stop_event = Event()
    
    def consume_messages(self):
        """
        Consume messages from Kafka topics and handle them with topic-specific methods.
        """
        logging.info(f"Starting Kafka consumer for topics: {self.topics}")
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=[self.kafka_url],
                security_protocol='SASL_PLAINTEXT',
                sasl_mechanism='PLAIN',
                sasl_plain_username=self.kafka_username,
                sasl_plain_password=self.kafka_password,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                value_deserializer=lambda x: x.decode('utf-8')
            )
            
            logging.info(f"Consumer created, subscribing to topics: {self.topics}")
            consumer.subscribe(self.topics)
            
            try:
                # Seek to the next offset for all partitions
                logging.info("Initial polling to get partition assignments")
                consumer.poll(timeout_ms=10000)
                for topic in self.topics:
                    partitions = consumer.partitions_for_topic(topic)
                    if partitions:
                        logging.info(f"Found partitions for topic {topic}: {partitions}")
                        for partition in partitions:
                            tp = TopicPartition(topic, partition)
                            consumer.seek_to_end(tp)
                            logging.info(f"Seeking to end for topic {topic}, partition {partition}")
                
                logging.info("Starting main consumer loop")
                while not self.stop_event.is_set():
                    msg_pack = consumer.poll(timeout_ms=1000)
                    
                    if self.stop_event.is_set():
                        logging.info("Stop event detected, breaking out of consumer loop")
                        break

                    if msg_pack:
                        logging.info(f"Received {sum(len(msgs) for msgs in msg_pack.values())} messages")
                        
                    for topic_partition, messages in msg_pack.items():
                        topic = topic_partition.topic
                        for message in messages:
                            value = message.value
                            logging.info(f"Message received from topic {topic}")
                            
                            # Get the handler for this topic
                            handler = self.handlers.get(topic)
                            if handler:
                                try:
                                    # Process message with handler
                                    handler(value, topic)
                                    logging.info(f"Message processed by handler for topic: {topic}")
                                except Exception as e:
                                    logging.error(f"Error in handler for topic {topic}: {e}")
                            else:
                                logging.warning(f"No handler found for topic: {topic}")
            except Exception as e:
                logging.error(f"Error in consumer loop: {e}")
        except Exception as e:
            logging.error(f"Error creating consumer: {e}")
        finally:
            logging.info("Closing consumer")
            try:
                consumer.close()
                logging.info("Consumer closed successfully")
            except Exception as e:
                logging.error(f"Error closing consumer: {e}")
    
    def start(self):
        """
        Start the Kafka consumer thread.
        """
        if self.thread and self.thread.is_alive():
            logging.info("Consumer thread already running.")
            return
        
        logging.info("Starting new consumer thread")
        self.stop_event.clear()
        self.thread = Thread(target=self.consume_messages)
        self.thread.start()
        logging.info("Consumer thread started.")
    
    def stop(self):
        """
        Stop the Kafka consumer thread.
        """
        logging.info("Stopping consumer")
        if self.thread and self.thread.is_alive():
            logging.info("Setting stop event")
            self.stop_event.set()
            
            # Wait for thread to join with timeout
            logging.info("Waiting for thread to join")
            self.thread.join(timeout=10)
            
            if self.thread.is_alive():
                logging.warning("Thread did not terminate within timeout, it may still be running")
            else:
                logging.info("Consumer thread stopped successfully")
        else:
            logging.info("Consumer thread not running.")