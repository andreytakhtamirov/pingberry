from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import os

class SMSNotification:
    def __init__(self):
        self.conf = ConnectionConfig(
            MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
            MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
            MAIL_FROM=os.getenv("MAIL_FROM"),
            MAIL_PORT=int(os.getenv("MAIL_PORT")),
            MAIL_SERVER=os.getenv("MAIL_SERVER"),
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True
        )
        self.mailer = FastMail(self.conf)

    async def send(self, email: str, message_from: str, message: str):
        msg = MessageSchema(
            subject="",
            recipients=[email],
            body=f"From: {message_from} \nLength: {len(message)}",
            subtype="plain"
        )
        await self.mailer.send_message(msg)
