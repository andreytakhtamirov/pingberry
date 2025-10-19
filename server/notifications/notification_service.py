from notifications.mqtt_notifier import MQTTNotification
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class NotificationService:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv("DB_PATH", "notification.db")

        self.mqtt_notifier = MQTTNotification(
            db_path=self.db_path,
            broker=os.getenv("MQTT_BROKER"),
            port=int(os.getenv("MQTT_PORT", "8883")),
            ca_cert=os.getenv("MQTT_CA_CERT"),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
        )

    def get_client_info(self, recipient_email: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT uuid, notification_public_key FROM clients WHERE email=?",
                (recipient_email,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "uuid": row[0],
                    "notification_public_key": row[1],
                }
        return None

    async def send_notification(self, message_to: str, message_from: str, message: str, queue_if_offline: bool):
        """
        Automatically selects the delivery method (currently only MQTT supported) based on device status.
        `to` is the device UUID.
        """
        client_info = self.get_client_info(message_to)
        if not client_info:
            # No client found in DB
            print(f"[WARN] Client info for {message_to} not found.")
            return {"method": None, "status": "fail", "code": 404, "error": f"Notification recipient {message_to} not found"}

        recipient_uuid = client_info["uuid"]
        notif_public_key_pem = client_info["notification_public_key"]

        try:
            if self.mqtt_notifier.is_device_online(recipient_uuid):
                print(f"[INFO] Device {recipient_uuid} online → sending via MQTT.")
                success = self.mqtt_notifier.send(
                    message_from, message, recipient_uuid, notif_public_key_pem
                )
                if success:
                    return {"method": "mqtt", "status": "success", "code": 200}
                else:
                    return {"method": "mqtt", "status": "fail", "code": 500, "error": "MQTT send failed"}
            else:
                if queue_if_offline:
                    print(f"[INFO] Queuing message for {recipient_uuid} until device comes online")
                    success = self.mqtt_notifier.send(
                        message_from, message, recipient_uuid, notif_public_key_pem
                    )
                    if success:
                        return {"method": "mqtt", "status": "success", "code": 200}
                    else:
                        return {"method": "mqtt", "status": "fail", "code": 500, "error": "MQTT queue failed"}

                return {"method": None, "status": "fail", "code": 409, "error": "Device offline"}

        except Exception as e:
            print(f"[ERROR] Notification send failed: {e}")
            return {"method": None, "status": "fail", "code": 500, "error": str(e)}
