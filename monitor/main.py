from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean
import os

# === Setup ===
app = FastAPI()
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

SERVICE_URL = "http://127.0.0.1:8080/status"

# === SQLite with SQLAlchemy ===
DATABASE_URL = "sqlite+aiosqlite:///status.db"
Base = declarative_base()

class StatusEntry(Base):
    __tablename__ = "statuses"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(String)
    mqtt_connected = Column(Boolean)
    uptime_seconds = Column(Integer)
    online_devices = Column(Integer)
    checked_at = Column(DateTime)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# === Global Status Cache ===
status_data = {
    "message": "Unknown",
    "mqtt_connected": False,
    "uptime_seconds": 0,
    "online_devices": 0,
    "last_checked": None
}

# === Background Task ===
async def fetch_status():
    async with httpx.AsyncClient() as client:
        now = datetime.now()
        try:
            response = await client.get(SERVICE_URL, timeout=5)
            response.raise_for_status()
            data = response.json()

            # Update in-memory status
            status_data.update({
                "message": data.get("message", "No message"),
                "mqtt_connected": data.get("mqtt_connected", False),
                "uptime_seconds": data.get("uptime_seconds"),
                "online_devices": data.get("online_devices", 0),
                "last_checked": now
            })

            # Save to DB
            async with async_session() as session:
                entry = StatusEntry(
                    message=status_data["message"],
                    mqtt_connected=status_data["mqtt_connected"],
                    uptime_seconds=status_data["uptime_seconds"],
                    online_devices=status_data["online_devices"],
                    checked_at=now
                )
                session.add(entry)
                await session.commit()

        except Exception as e:
            # Handle offline/unreachable state
            status_data.update({
                "message": f"Offline: {str(e)}",
                "mqtt_connected": False,
                "uptime_seconds": None,
                "online_devices": 0,
                "last_checked": now
            })

            async with async_session() as session:
                entry = StatusEntry(
                    message=status_data["message"],
                    mqtt_connected=False,
                    uptime_seconds=None,
                    online_devices=0,
                    checked_at=now
                )
                session.add(entry)
                await session.commit()

# === Periodic Status Checker ===
async def periodic_check():
    while True:
        await fetch_status()
        await asyncio.sleep(60 * 5)  # poll every 5 minutes

# === FastAPI Events ===
@app.on_event("startup")
async def startup_event():
    await asyncio.sleep(10)  # delay for service startup

    db_path = "status.db"
    if os.path.exists(db_path):
        os.remove(db_path)  # delete existing DB file

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # recreate tables

    asyncio.create_task(periodic_check())  # start background task

# === Routes ===
@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

@app.get("/status/notification-service")
async def serve_index():
    return FileResponse("static/notification-service-status.html")

@app.get("/status")
async def get_current_status():
    """Return the most recent status snapshot."""
    return JSONResponse({
        "message": status_data["message"],
        "mqtt_connected": status_data["mqtt_connected"],
        "uptime_seconds": status_data["uptime_seconds"],
        "online_devices": status_data["online_devices"],
        "last_checked": status_data["last_checked"].strftime("%Y-%m-%d %H:%M:%S") if status_data["last_checked"] else None
    })

@app.get("/history")
async def get_history():
    async with async_session() as session:
        result = await session.execute(
            StatusEntry.__table__.select().order_by(StatusEntry.checked_at.desc()).limit(30)
        )
        rows = result.fetchall()
        rows = rows[::-1]  # oldest first

        data = [{
            "checked_at": row.checked_at.strftime("%Y-%m-%d %H:%M:%S"),
            "message": row.message,
            "mqtt_connected": row.mqtt_connected,
            "uptime_seconds": row.uptime_seconds,
            "online_devices": row.online_devices
        } for row in rows]

        return data
