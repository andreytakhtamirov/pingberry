from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Client(Base):
    __tablename__ = "clients"

    uuid = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    notification_public_key = Column(String, nullable=False)
    status_public_key = Column(String, nullable=False)
    last_seen_online = Column(DateTime, nullable=True)

class IOSDevice(Base):
    __tablename__ = "ios_devices"

    email = Column(String, primary_key=True, index=True)
    device_token = Column(String, nullable=False)
    last_registered = Column(DateTime, nullable=True)

class PendingRegistration(Base):
    __tablename__ = "pending_registrations"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    device_type = Column(String, nullable=False)   # "ios" | "blackberry"
    code_hash = Column(String, nullable=False)
    payload = Column(String, nullable=False)       # JSON of the held registration
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
