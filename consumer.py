import os
import threading
import json
import logging
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pika
import nltk
import time

nltk.download('punkt')

app = Flask(__name__)
CORS(app)

# RabbitMQ configuration
rabbitmq_host = os.environ.get('RABBITMQ_HOST', '172.18.0.2')

response_lock = threading.Lock()
responses = {}
consumer_event = threading.Event()

connection = None
channel = None

def connect_to_rabbitmq():
    global connection, channel
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host))
        channel = connection.channel()
        channel.queue_declare(queue='chatbot', durable=True)  # Ensure queue is declared
    except Exception as e:
        logging.error(f"Failed to connect to RabbitMQ: {e}")

def start_consuming():
    global channel
    while consumer_event.is_set():
        try:
            if channel is None or channel.is_closed:
                logging.error("Channel is closed or None, trying to reconnect...")
                connect_to_rabbitmq()
            
            channel.basic_consume(queue='chatbot', on_message_callback=callback, auto_ack=True)
            logging.info("Started consuming messages.")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Connection lost: {e}. Retrying in 10 seconds...")
            time.sleep(10)
            connect_to_rabbitmq()
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

def wait_for_rabbitmq():
    while True:
        try:
            connect_to_rabbitmq()
            break  # Exit if successful
        except pika.exceptions.AMQPConnectionError:
            logging.info("Waiting for RabbitMQ...")
            time.sleep(5)

@app.route("/", methods=["GET"])
def index_get():
    return render_template("base.html")

def callback(ch, method, properties, body):
    try:
        response = json.loads(body.decode())
        uuid_key = response.get('uuid')
        response_value = response.get('response')
        
        if uuid_key and response_value is not None:
            with response_lock:
                responses[uuid_key] = response_value
        else:
            logging.error("Invalid message format: %s", response)
    except json.JSONDecodeError:
        logging.error("JSON decode error: %s", body.decode())
    except Exception as e:
        logging.error(f"Error processing message: {e}")

logging.basicConfig(level=logging.INFO)
wait_for_rabbitmq()  # Initial connection attempt
consumer_event.set()  # Start the consumer thread
consumer_thread = threading.Thread(target=start_consuming)
consumer_thread.daemon = True
consumer_thread.start()

@app.post("/predict")
def predict():
    global connection, channel 

    if channel is None or channel.is_closed:
        connect_to_rabbitmq()

    try:
        text = request.get_json().get("message")
        if not text:
            return jsonify({"error": "No message provided"}), 400

        # Attempt to publish the message
        try:
            channel.basic_publish(
                exchange='',
                routing_key='chatbot',
                body=json.dumps({"message": text}),
                properties=pika.BasicProperties(
                    content_type='application/json',
                    delivery_mode=2,
                )
            )
            logging.info(f"Sent message to RabbitMQ: {text}")

        except pika.exceptions.ChannelClosed:
            logging.error("Channel closed, attempting to reconnect...")
            connect_to_rabbitmq()  # Try to reconnect
            return jsonify({"error": "Channel closed, please try again"}), 503

        except Exception as e:
            logging.error(f"Unexpected error while publishing: {e}")
            return jsonify({"error": "Internal server error"}), 500

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
