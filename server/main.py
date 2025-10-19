from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models import NotificationRequest, RegisterRequest
from notifications.notification_service import NotificationService
from schemas import Client, Base
from db import SessionLocal, engine
from dotenv import load_dotenv
import os
from fastapi.responses import JSONResponse
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
async def notify(request: NotificationRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        notifier.send_notification, request.phone_email, request.message_from, request.message
    )
    return {"message": f"Notification sent to {request.phone_email}"}

@app.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Client).filter_by(uuid=str(request.uuid)).first()

    if existing:
        # Rotate both keys
        existing.email = request.email
        existing.notification_public_key = request.notification_public_key
        existing.status_public_key = request.status_public_key
        db.commit()
        return JSONResponse(
            content={"message": "Client updated (keys rotated)"},
            status_code=status.HTTP_200_OK
        )

    client = Client(
        uuid=str(request.uuid),
        email=request.email,
        notification_public_key=request.notification_public_key,
        status_public_key=request.status_public_key
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    return JSONResponse(
        content={"message": "Client registered successfully"},
        status_code=status.HTTP_201_CREATED
    )

@app.get("/status")
async def get_status():
    online_count = sum(1 for status in notifier.mqtt_notifier.device_statuses.values() if status)
    uptime_seconds = int(time.time() - start_time)
    return {
        "message": "OK",
        "mqtt_connected": notifier.mqtt_notifier.is_connected(),
        "uptime_seconds": uptime_seconds,
        "online_devices": online_count
    }