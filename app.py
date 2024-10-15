import os
import threading
import json
import logging
import uuid
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pika
import nltk
import time
from chat import get_response

nltk.download('punkt')

app = Flask(__name__)
CORS(app)
response_queue = []
rabbitmq_host = os.environ.get('RABBITMQ_HOST', '172.18.0.2')
def send_message(message):

    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host))
    channel = connection.channel()
    channel.queue_declare(queue='chat_queue', durable=True)
    channel.basic_publish(
        exchange='',
        routing_key='chat_queue',
        body=message,
        properties=pika.BasicProperties(delivery_mode=2)
    )
    connection.close()

def consume_messages():
    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host))
    channel = connection.channel()
    channel.queue_declare(queue='chat_queue', durable=True)

    def callback(ch, method, properties, body):
        message = body.decode()
        response = get_response(message)
        response_queue.append(response)
        print(f"Received: {message}, Response: {response}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue='chat_queue', on_message_callback=callback)
    channel.start_consuming()

# Start the consumer in a separate thread
threading.Thread(target=consume_messages, daemon=True).start()

@app.route("/", methods=["GET"])
def index_get():
    return render_template("base.html")


@app.post("/predict")
def predict():
    text = request.get_json().get("message")
    send_message(text)
    return jsonify({"status": "message sent"})

@app.get("/get_response")
def get_response_endpoint():
    if response_queue:
        response = response_queue.pop(0)  # Lấy phản hồi đầu tiên và xóa nó khỏi hàng đợi
        return jsonify({"response": response})
    return jsonify({"response": None})  # Nếu không có phản hồi nào

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
