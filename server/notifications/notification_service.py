from notifications.mqtt_notifier import MQTTNotification
from notifications.apns_notifier import APNSNotification
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

        self.apns_notifier = APNSNotification(
            team_id=os.getenv("APNS_TEAM_ID"),
            key_id=os.getenv("APNS_KEY_ID"),
            private_key_path=os.getenv("APNS_PRIVATE_KEY_PATH"),
            topic=os.getenv("APNS_TOPIC"),
            use_sandbox=os.getenv("APNS_USE_SANDBOX", "true").lower() in ("1", "true", "yes"),
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

    def get_ios_device(self, recipient_email: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT device_token FROM ios_devices WHERE email=?",
                (recipient_email,),
            )
            row = cursor.fetchone()
            if row:
                return {"device_token": row[0]}
        return None

    async def send_verification_code(self, email: str, code: str, via: str) -> bool:
        """Send a verification code to the existing device for `email` via the given channel."""
        title = "PingBerry verification code"
        body = f"Your verification code is {code}"

        if via == "blackberry":
            info = self.get_client_info(email)
            if not info:
                print(f"[WARN] No BlackBerry client for {email} to deliver verification code.")
                return False
            return self.mqtt_notifier.send(
                title, body, info["uuid"], info["notification_public_key"], False
            )

        if via == "ios":
            device = self.get_ios_device(email)
            if not device:
                print(f"[WARN] No iOS device for {email} to deliver verification code.")
                return False
            return await self.apns_notifier.send(title, body, device["device_token"])

        return False

    async def _deliver_mqtt(self, client_info, message_title, message_body, queue_if_offline, collapse_duplicates):
        """Deliver a plaintext notification to a BlackBerry 10 client via MQTT."""
        recipient_uuid = client_info["uuid"]
        notif_public_key_pem = client_info["notification_public_key"]

        try:
            if self.mqtt_notifier.is_device_online(recipient_uuid):
                print(f"[INFO] Device {recipient_uuid} online → sending via MQTT.")
                success = self.mqtt_notifier.send(
                    message_title, message_body, recipient_uuid, notif_public_key_pem, collapse_duplicates
                )
                if success:
                    return {"method": "mqtt", "status": "success", "code": 200}
                else:
                    return {"method": "mqtt", "status": "fail", "code": 500, "error": "MQTT send failed"}
            else:
                if queue_if_offline:
                    print(f"[INFO] Queuing message for {recipient_uuid} until device comes online")
                    success = self.mqtt_notifier.send(
                        message_title, message_body, recipient_uuid, notif_public_key_pem, collapse_duplicates
                    )
                    if success:
                        return {"method": "mqtt", "status": "success", "code": 202}
                    else:
                        return {"method": "mqtt", "status": "fail", "code": 500, "error": "MQTT queue failed"}

                return {"method": None, "status": "fail", "code": 409, "error": "Device offline"}

        except Exception as e:
            print(f"[ERROR] Notification send failed: {e}")
            return {"method": None, "status": "fail", "code": 500, "error": str(e)}

    async def send_notification(self, recipient_email: str, message_title: str, message_body: str, queue_if_offline: bool, collapse_duplicates: bool):
        """
        Deliver a plaintext notification to every device registered for the
        recipient email: BlackBerry 10 clients via MQTT and iOS devices via APNs.
        """
        client_info = self.get_client_info(recipient_email)
        ios_device = self.get_ios_device(recipient_email)

        if not client_info and not ios_device:
            print(f"[WARN] Client info for {recipient_email} not found.")
            return {"method": None, "status": "fail", "code": 404, "error": f"Notification recipient {recipient_email} not found"}

        methods = []
        errors = []
        queued = False

        # 1) BlackBerry 10 clients via MQTT.
        if client_info:
            mqtt_result = await self._deliver_mqtt(client_info, message_title, message_body, queue_if_offline, collapse_duplicates)
            if mqtt_result["status"] == "success":
                methods.append("mqtt")
                if mqtt_result["code"] == 202:
                    queued = True
            else:
                errors.append(mqtt_result.get("error", "MQTT send failed"))

        # 2) iOS devices via APNs.
        if ios_device:
            apns_ok = await self.apns_notifier.send(message_title, message_body, ios_device["device_token"])
            if apns_ok:
                methods.append("apns")
            else:
                errors.append("APNs send failed")

        if methods:
            code = 202 if (queued and "apns" not in methods) else 200
            return {"method": ",".join(methods), "status": "success", "code": code}

        return {"method": None, "status": "fail", "code": 409, "error": "; ".join(errors) if errors else "No delivery method available"}

    async def send_encrypted_notification(self, recipient_email: str, encrypted_title: str, encrypted_body: str, queue_if_offline: bool, collapse_duplicates: bool):
        client_info = self.get_client_info(recipient_email)
        if not client_info:
            print(f"[WARN] Client info for {recipient_email} not found.")
            return {"method": None, "status": "fail", "code": 404, "error": f"Notification recipient {recipient_email} not found"}

        recipient_uuid = client_info["uuid"]
        notif_public_key_pem = client_info["notification_public_key"]

        try:
            if self.mqtt_notifier.is_device_online(recipient_uuid):
                print(f"[INFO] Device {recipient_uuid} online → sending via MQTT.")
                success = self.mqtt_notifier.send_encrypted(
                    encrypted_title, encrypted_body, recipient_uuid, notif_public_key_pem, collapse_duplicates
                )
                if success:
                    return {"method": "mqtt", "status": "success", "code": 200}
                else:
                    return {"method": "mqtt", "status": "fail", "code": 500, "error": "MQTT send failed"}
            else:
                if queue_if_offline:
                    print(f"[INFO] Queuing message for {recipient_uuid} until device comes online")
                    success = self.mqtt_notifier.send_encrypted(
                        encrypted_title, encrypted_body, recipient_uuid, notif_public_key_pem, collapse_duplicates
                    )
                    if success:
                        return {"method": "mqtt", "status": "success", "code": 202}
                    else:
                        return {"method": "mqtt", "status": "fail", "code": 500, "error": "MQTT queue failed"}

                return {"method": None, "status": "fail", "code": 409, "error": "Device offline"}

        except Exception as e:
            print(f"[ERROR] Notification send failed: {e}")
            return {"method": None, "status": "fail", "code": 500, "error": str(e)}
