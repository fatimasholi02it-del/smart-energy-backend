from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from database import Base


class EnergyReading(Base):
    __tablename__ = "energy_readings"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, index=True, nullable=False)
    energy = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, nullable=True)
    room_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    raw_payload = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False)