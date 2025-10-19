from pydantic import BaseModel, EmailStr
from enum import Enum
from uuid import UUID
from typing import Optional

class NotificationMethod(str, Enum):
    mqtt = "mqtt"

class NotificationRequest(BaseModel):
    recipient_email: EmailStr
    message_title: str
    message_body: str
    method: NotificationMethod = NotificationMethod.mqtt
    queue_if_offline: bool = False
    collapse_duplicates: bool = True

class EncryptedNotificationRequest(BaseModel):
    recipient_email: EmailStr
    encrypted_title: str
    encrypted_body: str
    method: NotificationMethod = NotificationMethod.mqtt
    queue_if_offline: bool = False
    collapse_duplicates: bool = True

class RegisterRequest(BaseModel):
    email: EmailStr
    uuid: UUID
    notification_public_key: str
    status_public_key: str 

class PublicKeyRequest(BaseModel):
    recipient_email: EmailStr

class PublicKeyResponse(BaseModel):
    notification_public_key: str
