from pydantic import BaseModel, EmailStr
from enum import Enum
from uuid import UUID
from typing import Optional

class NotificationMethod(str, Enum):
    mqtt = "mqtt"

class NotificationRequest(BaseModel):
    phone_email: EmailStr
    message_from: str
    message: str
    method: NotificationMethod
    queue_if_offline: bool = False

class RegisterRequest(BaseModel):
    email: EmailStr
    uuid: UUID
    notification_public_key: str
    status_public_key: str 

