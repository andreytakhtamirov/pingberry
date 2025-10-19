from notifications.mqtt_notifier import MQTTNotification
from notifications.sms_notifier import SMSNotification
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
        self.sms_notifier = SMSNotification()

    def get_client_info(self, recipient_email: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT uuid, notification_public_key, sms_fallback FROM clients WHERE email=?",
                (recipient_email,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "uuid": row[0],
                    "notification_public_key": row[1],
                    "sms_fallback": row[2],
                }
        return None

    async def send_notification(self, message_to: str, message_from: str, message: str):
        """
        Automatically selects the delivery method (MQTT or SMS) based on device status.
        `to` is the device UUID.
        """
        client_info = self.get_client_info(message_to)
        if not client_info:
            # No client found in DB — fallback to SMS or return failure
            print(f"[WARN] Client info for {message_to} not found, sending SMS fallback.")
            try:
                await self.sms_notifier.send(message_to, message_from, message)
                return {"method": "sms", "status": "success", "code": 200}
            except Exception as e:
                return {"method": None, "status": "fail", "code": 500, "error": str(e)}

        recipient_uuid = client_info["uuid"]
        notif_public_key_pem = client_info["notification_public_key"]
        sms_fallback = client_info["sms_fallback"]

        try:
            if self.mqtt_notifier.is_device_online(recipient_uuid):
                print(f"[INFO] Device {recipient_uuid} online → sending via MQTT.")
                success = self.mqtt_notifier.send(
                    message_from, message, recipient_uuid, notif_public_key_pem
                )
                if success:
                    return {"method": "mqtt", "status": "success", "code": 200}
                else:
                    print(f"[WARN] MQTT send failed for {recipient_uuid}. Falling back to SMS.")
            else:
                print(f"[WARN] Device {recipient_uuid} offline → fallback to SMS.")
            
            # SMS fallback
            if sms_fallback:
                print(f"[INFO] Using SMS fallback for {recipient_uuid} → {sms_fallback}")
                sms_result = await self.sms_notifier.send(sms_fallback, message_from, message)
                return sms_result
            else:
                print("[ERROR] No SMS fallback configured.")
                return {
                    "method": None,
                    "status": "fail",
                    "code": 503,
                    "error": "Device offline and no SMS fallback available",
                }

        except Exception as e:
            print(f"[ERROR] Notification send failed: {e}")
            return {"method": None, "status": "fail", "code": 500, "error": str(e)}
