from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import os

def str_to_bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")

class SMSNotification:
    def __init__(self):
        # Configure email (used as SMS gateway or fallback)
        self.conf = ConnectionConfig(
            MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
            MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
            MAIL_FROM=os.getenv("MAIL_FROM"),
            MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
            MAIL_SERVER=os.getenv("MAIL_SERVER"),
            MAIL_STARTTLS=str_to_bool(os.getenv("MAIL_STARTTLS"), True),
            MAIL_SSL_TLS=str_to_bool(os.getenv("MAIL_SSL_TLS"), False),
            USE_CREDENTIALS=True
        )
        self.mailer = FastMail(self.conf)

    async def send(self, email: str, message_from: str, message: str):
        """
        Sends an SMS (via email-to-SMS gateway) or email fallback.
        Returns structured result for consistent handling.
        """
        msg = MessageSchema(
            subject=f"Notification from {message_from}",
            recipients=[email],
            body=f"From: {message_from}\n\nMessage:\n{message}",
            subtype="plain",
        )

        try:
            await self.mailer.send_message(msg)
            print(f"SMSNotification: message sent to {email}")
            return {"status": "success", "method": "sms", "code": 200}
        except Exception as e:
            print(f"SMSNotification: failed to send to {email}: {e}")
            return {"status": "fail", "method": "sms", "code": 500, "error": str(e)}
