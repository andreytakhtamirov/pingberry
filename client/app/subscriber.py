import paho.mqtt.client as mqtt
import ssl
import time
import json
import threading
import uuid
import argparse
from pathlib import Path
import rsa
import base64
import fcntl
import os

# --------- Utilities ---------
def log(msg):
    print(msg)

def load_client_data(path):
    path = Path(path)
    if not path.exists():
        log(f"Client data file not found: {path}")
        exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data

def load_credentials(path):
    path = Path(path)
    if not path.exists():
        log(f"MQTT credentials file not found: {path}")
        exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data

def load_keys(client_data):
    notif_priv_key = rsa.PrivateKey.load_pkcs1(client_data["notification_private_key"].encode())
    status_priv_key = rsa.PrivateKey.load_pkcs1(client_data["status_private_key"].encode())
    return notif_priv_key, status_priv_key

def decrypt_payload(encrypted_b64: str, private_key: rsa.PrivateKey) -> str:
    """
    Decrypts a base64-encoded RSA-encrypted payload. Raises on failure.
    """
    ciphertext = base64.b64decode(encrypted_b64)
    decrypted = rsa.decrypt(ciphertext, private_key)
    return decrypted.decode()

def safe_send_notification(itemid, title, subtitle, target, target_action,
                           payload_field, payload_type, payload_uri,
                           control_path="/pps/services/notify/control"):
    """
    Safely write the notification command to the PPS control file using an exclusive file lock.
    Builds JSON for the `dat` field to avoid shell injection.
    """
    msg = {
        "msg": "notify",
        "dat": {
            "itemid": itemid,
            "title": title,
            "subtitle": subtitle,
            "target": target,
            "targetAction": target_action,
            "payload": payload_field,
            "payloadType": payload_type,
            "payloadURI": payload_uri
        }
    }

    dat_json = json.dumps(msg["dat"], separators=(",", ":"), ensure_ascii=False)
    full_message = f"msg::notify\ndat:json:{dat_json}\n"

    try:
        with open("/pps/services/notify/control", "a", encoding="utf-8") as f:
            # Acquire exclusive lock while writing
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(full_message)
            f.flush()
            os.fsync(f.fileno())
            # Lock is released when file is closed
    except Exception as e:
        log(f"Failed to write notify message: {e}")

def make_signed_status_payload(status: bool, private_key: rsa.PrivateKey) -> str:
    payload = json.dumps({"status": status})
    signature = rsa.sign(payload.encode(), private_key, 'SHA-256')
    return json.dumps({
        "payload": payload,
        "signature": base64.b64encode(signature).decode()
    })

def on_connect(client, userdata, flags, reasonCode, properties):
    log(f"Connected: {reasonCode}")
    log(f"Subscribing to: {userdata['topic']}")
    client.subscribe(userdata['topic'], qos=1)

    client.publish(
        topic=userdata['status_topic'],
        payload=make_signed_status_payload(True, userdata['status_pk']),
        qos=1,
        retain=True
    )

def on_disconnect(client, userdata, flags, reasonCode, properties):
    log(f"Disconnected: {reasonCode}")

def on_message(client, userdata, msg):
    log(f"Received message on {msg.topic}")
    notif_private_key = userdata["notif_pk"]

    try:
        payload_data = json.loads(msg.payload.decode())

        # Required encrypted fields
        encrypted_itemid = payload_data.get("itemid")
        encrypted_title = payload_data.get("title")
        encrypted_subtitle = payload_data.get("subtitle")

        if not all([encrypted_itemid, encrypted_title, encrypted_subtitle]):
            log("Missing required encrypted fields; ignoring message.")
            return

        # Try to decrypt all payloads; if any fail, ignore message completely
        try:
            itemid = decrypt_payload(encrypted_itemid, notif_private_key)
            title = decrypt_payload(encrypted_title, notif_private_key)
            subtitle = decrypt_payload(encrypted_subtitle, notif_private_key)
        except Exception as e:
            log(f"Decryption failed, ignoring message: {e}")
            return

        # Other (non-encrypted) metadata
        target = payload_data.get("target", "defaultTarget")
        target_action = payload_data.get("targetAction", "defaultTargetAction")
        payload_field = payload_data.get("payload", "defaultPayload")
        payload_type = payload_data.get("payloadType", "defaultPayloadType")
        payload_uri = payload_data.get("payloadURI", "defaultPayloadURI")

        # Send to PPS safely in a background thread
        threading.Thread(
            target=safe_send_notification,
            args=(itemid, title, subtitle, target, target_action, payload_field, payload_type, payload_uri)
        ).start()

    except Exception as e:
        log(f"Error processing message: {e}")

def main():
    parser = argparse.ArgumentParser(description="MQTT Notification Subscriber")
    parser.add_argument(
        "--client-data",
        default="client_data.json",
        help="Path to client data JSON file (default: client_data.json)"
    )

    parser.add_argument(
        "--mqtt-credentials",
        default="client_data.json",
        help="Path to MQTT credentials JSON file (default: mqtt_credentials.json)"
    )

    args = parser.parse_args()

    creds = load_credentials(args.mqtt_credentials)
    MQTT_BROKER = creds["MQTT_BROKER"]
    MQTT_PORT = creds["MQTT_PORT"]
    MQTT_USERNAME = creds["MQTT_USERNAME"]
    MQTT_PASSWORD = creds["MQTT_PASSWORD"]

    client_data = load_client_data(args.client_data)
    uuid_str = client_data["uuid"]
    notif_private_key, status_private_key = load_keys(client_data)

    notification_topic = f"notifications/{uuid_str}"
    status_topic = f"status/{uuid_str}"

    mqtt_client = mqtt.Client(
        transport="websockets",
        protocol=mqtt.MQTTv5,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=str(uuid.uuid4())
    )

    mqtt_client.tls_set()
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    mqtt_client.will_set(
        topic=status_topic,
        payload=make_signed_status_payload(False, status_private_key),
        qos=1,
        retain=True
    )

    mqtt_client.user_data_set({
        "uuid": uuid_str,
        "topic": notification_topic,
        "status_topic": status_topic,
        "notif_pk": notif_private_key,
        "status_pk": status_private_key
    })

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqtt_client.loop_forever()

if __name__ == "__main__":
    main()
