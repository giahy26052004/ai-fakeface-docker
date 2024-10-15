import pika
import os
import time

rabbitmq_host = os.environ.get('RABBITMQ_HOST', 'rabbitmq')

# Đợi một chút để đảm bảo RabbitMQ đã khởi động
time.sleep(5)

try:
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
    print("Connected to RabbitMQ!")
    connection.close()
except Exception as e:
    print(f"Failed to connect to RabbitMQ: {e}")
