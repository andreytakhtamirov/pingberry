from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models import NotificationRequest, RegisterRequest, PublicKeyRequest, PublicKeyResponse, EncryptedNotificationRequest
from notifications.notification_service import NotificationService
from schemas import Client, Base
from db import SessionLocal, engine
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from util.validate import Validate
import os
import time

load_dotenv()

start_time = time.time()
app = FastAPI()

notifier = NotificationService(db_path=os.getenv("DB_PATH", "notification.db"))

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/notify")
async def send_notification(request: NotificationRequest):
    # Validate each field separately for clear error messages
    Validate.check_field_length(request.message_title, "message_title")
    Validate.check_field_length(request.message_body, "message_body")

    # Continue with notification sending
    result = await notifier.send_notification(
        request.recipient_email,
        request.message_title,
        request.message_body,
        request.queue_if_offline,
        request.collapse_duplicates,
    )

    if result["status"] == "success":
        return JSONResponse(
            content={
                "message": f"Notification sent via {result['method']}",
                "details": result,
            },
            status_code=result["code"],
        )

    return JSONResponse(
        content={
            "message": "Notification failed",
            "details": result.get("error", "Unknown error"),
        },
        status_code=result["code"],
    )

@app.post("/notify/encrypted")
async def send_encrypted_notification(request: EncryptedNotificationRequest):
    """
    Send an encrypted notification to a registered client device.
    The title and body must be pre-encrypted by the sender.
    """
    result = await notifier.send_encrypted_notification(
        request.recipient_email,
        request.encrypted_title,
        request.encrypted_body,
        request.queue_if_offline,
        request.collapse_duplicates,
    )

    if result["status"] == "success":
        return JSONResponse(
            content={
                "message": f"Notification sent via {result['method']}",
                "details": result,
            },
            status_code=result["code"],
        )

    return JSONResponse(
        content={
            "message": "Notification failed",
            "details": result.get("error", "Unknown error"),
        },
        status_code=result["code"],
    )

@app.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing_by_uuid = db.query(Client).filter_by(uuid=str(request.uuid)).first()
    existing_by_email = db.query(Client).filter_by(email=request.email).first()

    # TODO in the future, key rotation could be allowed only if we can verify the client to prevent hijacking (e.g., sending a link via email).
    if existing_by_uuid:
        # Block any attempts to overwrite an existing client
        raise HTTPException(
            status_code=409,
            detail="This device and email are already registered. Key rotation or overwrite not allowed.",
        )
    if existing_by_email:
        raise HTTPException(
            status_code=409,
            detail="This email is already registered to another device. Overwrite is not allowed.",
        )

    # Create a new registration
    client = Client(
        uuid=str(request.uuid),
        email=request.email,
        notification_public_key=request.notification_public_key,
        status_public_key=request.status_public_key,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    return JSONResponse(
        content={"message": "Client registered successfully"},
        status_code=status.HTTP_201_CREATED,
    )

@app.post("/clients/public-key", response_model=PublicKeyResponse)
def get_public_key(request: PublicKeyRequest, db: Session = Depends(get_db)):
    client = db.query(Client).filter_by(email=request.recipient_email).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    return PublicKeyResponse(
        notification_public_key=client.notification_public_key,
    )

@app.get("/status")
async def get_status():
    online_count = sum(
        1 for status in notifier.mqtt_notifier.device_statuses.values() if status
    )
    uptime_seconds = int(time.time() - start_time)
    return {
        "message": "OK",
        "mqtt_connected": notifier.mqtt_notifier.is_connected(),
        "uptime_seconds": uptime_seconds,
        "online_devices": online_count,
    }
