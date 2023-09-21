from awscrt import mqtt, http
from awsiot import mqtt_connection_builder
import sys
import threading
import time
import json

# from awscrt.mqtt5 import Client as LocalMqttClient

received_count = 0
received_all_event = threading.Event()


# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    print("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))


# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    print("Received message from topic '{}': {}".format(topic, payload))
    global received_count
    received_count += 1
    if received_count == 0:
        received_all_event.set()


# Callback when the connection successfully connects
def on_connection_success(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionSuccessData)
    print("Connection Successful with return code: {} session present: {}".format(callback_data.return_code, callback_data.session_present))


# Callback when a connection attempt fails
def on_connection_failure(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionFailuredata)
    print("Connection failed with error code: {}".format(callback_data.error))


# Callback when a connection has been disconnected or shutdown successfully
def on_connection_closed(connection, callback_data):
    print("Connection closed")


# Create a MQTT connection from the command line data
mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint="a1poqnhtwgj0le-ats.iot.eu-north-1.amazonaws.com",
    cert_filepath="certs/Enterer_Device1.cert.pem",
    pri_key_filepath="certs/Enterer_Device1.private.key",
    ca_filepath="certs/root-CA.crt",
    on_connection_interrupted=on_connection_interrupted,
    on_connection_resumed=on_connection_resumed,
    client_id="basicPubSub",
    clean_session=False,
    keep_alive_secs=30,
    on_connection_success=on_connection_success,
    on_connection_failure=on_connection_failure,
    on_connection_closed=on_connection_closed)

# Hier soll es dann weiter auf den LOKALEN MQTT-Broker gehen
#local_mqtt_connection = mqtt_connection_builder.mtls_from_path(
#    endpoint="localhost",
#    on_connection_interrupted=on_local_connection_interrupted,
#    on_connection_resumed=on_local_connection_resumed,
#    clean_session=False,
#    keep_alive_secs=30,
#    on_connection_success=on_loccal_connection_success,
#    on_connection_failure=on_local_connection_failure,
#    on_connection_closed=on_local_connection_closed)

connect_future = mqtt_connection.connect()

# Future.result() waits until a result is available
connect_future.result()
print("Connected!")

message_count = 0
message_topic = "sdk/test/python"
message_string = "OWASYS Test Message from Docker Image"

print("Subscribing to topic '{}'...".format(message_topic))
subscribe_future, packet_id = mqtt_connection.subscribe(
    topic=message_topic,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_message_received)

subscribe_result = subscribe_future.result()
print("Subscribed with {}".format(str(subscribe_result['qos'])))

if message_string:
    if message_count == 0:
        print("Sending messages until program killed")
    else:
        print("Sending {} message(s)".format(message_count))

    publish_count = 1
    while (publish_count <= message_count) or (message_count == 0):
        message = "{} [{}]".format(message_string, publish_count)
        print("Publishing message to topic '{}': {}".format(message_topic, message))
        message_json = json.dumps(message)
        mqtt_connection.publish(
            topic=message_topic,
            payload=message_json,
            qos=mqtt.QoS.AT_LEAST_ONCE)
        time.sleep(1)
        publish_count += 1

# Wait for all messages to be received.
# This waits forever if count was set to 0.
if message_count != 0 and not received_all_event.is_set():
    print("Waiting for all messages to be received...")

received_all_event.wait()
print("{} message(s) received.".format(received_count))

# Disconnect
print("Disconnecting...")
disconnect_future = mqtt_connection.disconnect()
disconnect_future.result()
print("Disconnected!")
