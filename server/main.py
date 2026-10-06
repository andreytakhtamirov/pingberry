from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models import NotificationRequest, RegisterRequest, PublicKeyRequest, PublicKeyResponse, EncryptedNotificationRequest, IOSRegisterRequest, ConfirmRequest
from notifications.notification_service import NotificationService
from schemas import Client, IOSDevice, PendingRegistration, Base
from db import SessionLocal, engine
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from util.validate import Validate
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import os
import time
import json
import secrets
import hashlib
import hmac

load_dotenv()

start_time = time.time()
app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

notifier = NotificationService(db_path=os.getenv("DB_PATH", "notification.db"))

# Create tables
Base.metadata.create_all(bind=engine)

CODE_TTL_MINUTES = 10
MAX_CODE_ATTEMPTS = 5


def _utcnow():
    """Naive UTC now, matching the other datetimes stored in this app."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def _challenge(db, email: str, device_type: str, payload: dict, deliver_via: str):
    """
    Require the registrant to prove they can read notifications on the device
    already registered for `email`. Generates a 6-digit code, sends it via the
    existing device's channel, and holds the new device's details until confirmed.
    """
    code = _generate_code()

    # Replace any existing pending challenge for this email + device type.
    db.query(PendingRegistration).filter_by(email=email, device_type=device_type).delete()

    pending_id = str(uuid4())
    db.add(PendingRegistration(
        id=pending_id,
        email=email,
        device_type=device_type,
        code_hash=_hash_code(code),
        payload=json.dumps(payload),
        created_at=_utcnow(),
        expires_at=_utcnow() + timedelta(minutes=CODE_TTL_MINUTES),
        attempts=0,
    ))

    sent = await notifier.send_verification_code(email, code, deliver_via)
    if not sent:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Could not deliver the verification code to your existing device. Please try again.",
        )

    db.commit()
    return JSONResponse(
        content={
            "status": "verification_required",
            "pending_id": pending_id,
            "challenge_delivered_via": deliver_via,
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


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
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Same device re-registering: block key rotation / overwrite.
    if db.query(Client).filter_by(uuid=str(request.uuid)).first():
        raise HTTPException(
            status_code=409,
            detail="This device is already registered. Key rotation or overwrite not allowed.",
        )

    existing_bb = db.query(Client).filter_by(email=request.email).first()
    existing_ios = db.query(IOSDevice).filter_by(email=request.email).first()

    if existing_bb or existing_ios:
        # Email already has a device → require verification via that device.
        deliver_via = "blackberry" if existing_bb else "ios"
        return await _challenge(
            db,
            request.email,
            "blackberry",
            {
                "uuid": str(request.uuid),
                "notification_public_key": request.notification_public_key,
                "status_public_key": request.status_public_key,
            },
            deliver_via,
        )

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


@app.post("/register/ios")
async def register_ios(request: IOSRegisterRequest, db: Session = Depends(get_db)):
    device_token = request.device_token.strip()
    if not device_token:
        raise HTTPException(
            status_code=400,
            detail="device_token must not be empty",
        )

    existing_ios = db.query(IOSDevice).filter_by(email=request.email).first()
    existing_bb = db.query(Client).filter_by(email=request.email).first()

    # Idempotent re-registration of the same device (e.g. on every app launch).
    if existing_ios and existing_ios.device_token == device_token:
        return JSONResponse(
            content={"message": "iOS device already registered"},
            status_code=status.HTTP_200_OK,
        )

    if existing_ios or existing_bb:
        # Email already has a device → require verification via that device.
        deliver_via = "ios" if existing_ios else "blackberry"
        return await _challenge(
            db,
            request.email,
            "ios",
            {"device_token": device_token},
            deliver_via,
        )

    db.add(IOSDevice(
        email=request.email,
        device_token=device_token,
        last_registered=_utcnow(),
    ))
    db.commit()
    return JSONResponse(
        content={"message": "iOS device registered"},
        status_code=status.HTTP_201_CREATED,
    )


@app.post("/register/confirm")
def confirm_registration(request: ConfirmRequest, db: Session = Depends(get_db)):
    pending = db.query(PendingRegistration).filter_by(id=request.pending_id).first()
    if not pending:
        raise HTTPException(
            status_code=404,
            detail="Verification request not found or already completed.",
        )

    if _utcnow() > pending.expires_at:
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=410,
            detail="Verification code expired. Please register again.",
        )

    if not hmac.compare_digest(pending.code_hash, _hash_code(request.code.strip())):
        pending.attempts += 1
        if pending.attempts >= MAX_CODE_ATTEMPTS:
            db.delete(pending)
            db.commit()
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect attempts. Please register again.",
            )
        db.commit()
        raise HTTPException(
            status_code=401,
            detail="Incorrect verification code.",
        )

    payload = json.loads(pending.payload)

    if pending.device_type == "ios":
        existing_ios = db.query(IOSDevice).filter_by(email=pending.email).first()
        if existing_ios:
            existing_ios.device_token = payload["device_token"]
            existing_ios.last_registered = _utcnow()
        else:
            db.add(IOSDevice(
                email=pending.email,
                device_token=payload["device_token"],
                last_registered=_utcnow(),
            ))
    else:  # blackberry
        # Replace any existing BlackBerry device registered to this email.
        db.query(Client).filter_by(email=pending.email).delete()
        db.add(Client(
            uuid=payload["uuid"],
            email=pending.email,
            notification_public_key=payload["notification_public_key"],
            status_public_key=payload["status_public_key"],
        ))

    db.delete(pending)
    db.commit()
    return JSONResponse(
        content={"message": "Device verified and registered"},
        status_code=status.HTTP_200_OK,
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
