from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Client(Base):
    __tablename__ = "clients"

    uuid = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    sms_fallback = Column(String, nullable=True)
    notification_public_key = Column(String, nullable=False)
    status_public_key = Column(String, nullable=False)
