import paho.mqtt.client as mqtt
import ssl
import time
import json
import random
import string
import uuid
import threading
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
import base64
import sqlite3

class MQTTNotification:
    def __init__(self, db_path, broker, port, ca_cert, username, password):
        self.db_path = db_path
        self.status_topic_filter = "status/+"
        self.device_statuses = {}  # device_uuid -> True/False
        self.connected = False
        self.subscribed = False

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            protocol=mqtt.MQTTv5,
            client_id=str(uuid.uuid4())
        )

        self.client.tls_set(ca_certs=ca_cert, tls_version=ssl.PROTOCOL_TLS)
        self.client.username_pw_set(username, password)

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_status_message

        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client.connect(broker, port, 30)
        self.client.loop_start()

    def verify_signed_status(self, payload_dict: dict, public_key_pem: str) -> bool:
        try:
            signature_b64 = payload_dict.get("signature")
            signed_payload = payload_dict.get("payload")
            if not signature_b64 or not signed_payload:
                return False

            signature = base64.b64decode(signature_b64)
            public_key = RSA.import_key(public_key_pem)
            h = SHA256.new(signed_payload.encode())

            pkcs1_15.new(public_key).verify(h, signature)
            return True
        except (ValueError, TypeError):
            return False

    def encrypt_message(self, public_key_pem: str, message: str) -> str:
        pubkey = RSA.import_key(public_key_pem)
        cipher = PKCS1_v1_5.new(pubkey)
        ciphertext = cipher.encrypt(message.encode())
        return base64.b64encode(ciphertext).decode()

    def on_connect(self, client, userdata, flags, reasonCode, properties):
        self.connected = True
        print("MQTT connected with reason code:", reasonCode)

        if not self.subscribed:
            client.subscribe(self.status_topic_filter)
            self.subscribed = True
            print(f"Subscribed to topic: {self.status_topic_filter}")
        else:
            print("Already subscribed; skipping duplicate subscription.")


    def on_disconnect(self, client, userdata, flags, reasonCode, properties):
        self.connected = False
        self.subscribed = False
        print(f"MQTT disconnected with reason code: {reasonCode}")
        self.device_statuses = {}

    def is_connected(self):
        return self.connected

    def get_status_public_key(self, device_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status_public_key FROM clients WHERE uuid=?", (device_id,))
            row = cursor.fetchone()
            if row:
                return row[0]
        return None

    def on_status_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            topic_parts = msg.topic.strip('/').split('/')
            if len(topic_parts) == 2 and topic_parts[0] == 'status':
                device_id = topic_parts[1]

                # Fetch status-public key from DB
                public_key_pem = self.get_status_public_key(device_id)
                if not public_key_pem:
                    print(f"No public key found for {device_id}")
                    return

                if not self.verify_signed_status(data, public_key_pem):
                    print(f"Invalid signature on status from {device_id}")
                    return

                payload = json.loads(data["payload"])
                status = bool(payload.get('status', False))
                self.device_statuses[device_id] = status
                print(f"Device '{device_id}' is now {'online' if status else 'offline'}")

        except Exception as e:
            print(f"Failed to parse status message: {e}")


    def generate_message_id(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    def create_payload(self, public_key_pem, message_from, message_text):
        # TODO add 245-byte per item payload limit.
        item_id_encrypted = self.encrypt_message(public_key_pem, self.generate_message_id())
        message_from_encrypted = self.encrypt_message(public_key_pem, message_from) #self.generate_message_id()
        payload_dict = {
            "itemid": message_from_encrypted,
            "title": message_from_encrypted,
            "subtitle": self.encrypt_message(public_key_pem, message_text),
            # "target": "defaultTarget",
            # "targetAction": "defaultTargetAction",
            # "payload": "defaultPayload",
            # "payloadType": "defaultPayloadType",
            # "payloadURI": "defaultPayloadURI"
        }
        return json.dumps(payload_dict)

    def is_device_online(self, device_uuid):
        return self.device_statuses.get(device_uuid, False)

    def send(self, message_from, message_text, recipient_uuid, public_key_pem):
        payload = self.create_payload(public_key_pem, message_from, message_text)

        topic = f"notifications/{recipient_uuid}"
        print(f"MQTT Publish to {topic}, From: {message_from}")
        info = self.client.publish(topic, payload, qos=1)
        info.wait_for_publish()

        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            print("MQTT message published successfully")
            return True
        else:
            print(f"MQTT publish failed: {info.rc}")
            return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
