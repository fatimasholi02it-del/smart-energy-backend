import json
import hmac
import hashlib
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

import models
from config import settings
from database import SessionLocal


last_timestamp_by_stream = {}
last_seen_by_device = {}


def save_security_event(event_type, reason, raw_payload=None, device_id=None, room_id=None):
    db: Session = SessionLocal()
    try:
        event = models.SecurityEvent(
            device_id=device_id,
            room_id=room_id,
            event_type=event_type,
            reason=reason,
            raw_payload=raw_payload,
            timestamp=datetime.now()
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        print(f"Security event saved: {event.event_type} - {event.reason}")
    except Exception as e:
        db.rollback()
        print(f"Failed to save security event: {e}")
    finally:
        db.close()


def build_signing_string(reading_data: dict) -> str:
    return f"{reading_data['device_id']}|{reading_data['room_id']}|{reading_data['energy']}|{reading_data['timestamp']}"


def generate_expected_signature(reading_data: dict) -> str:
    signing_string = build_signing_string(reading_data)
    return hmac.new(
        settings.message_secret.encode(),
        signing_string.encode(),
        hashlib.sha256
    ).hexdigest()


def is_replay_attack(device_id: str, room_id: str, message_timestamp: str) -> bool:
    current_ts = datetime.fromisoformat(message_timestamp)
    stream_key = (device_id, room_id)
    last_ts = last_timestamp_by_stream.get(stream_key)

    if last_ts is not None and current_ts <= last_ts:
        return True

    return False


def update_last_seen_timestamp(device_id: str, room_id: str, message_timestamp: str):
    stream_key = (device_id, room_id)
    last_timestamp_by_stream[stream_key] = datetime.fromisoformat(message_timestamp)


def update_device_last_seen(device_id: str):
    last_seen_by_device[device_id] = datetime.now()


def validate_reading(reading_data: dict):
    errors = []

    required_fields = ["device_id", "room_id", "energy", "timestamp", "signature"]

    for field in required_fields:
        if field not in reading_data:
            errors.append({
                "event_type": "missing_field",
                "reason": f"Missing field: {field}"
            })

    if errors:
        return False, errors

    device_id = reading_data["device_id"]
    room_id = reading_data["room_id"]
    energy = reading_data["energy"]
    timestamp = reading_data["timestamp"]
    provided_signature = reading_data["signature"]

    if device_id not in settings.trusted_devices:
        errors.append({
            "event_type": "unknown_device",
            "reason": f"Unknown device_id: {device_id}"
        })

    room_is_known = room_id in settings.allowed_rooms
    if not room_is_known:
        errors.append({
            "event_type": "unknown_room",
            "reason": f"Unknown room_id: {room_id}"
        })

    energy_is_numeric = isinstance(energy, (int, float))
    if not energy_is_numeric:
        errors.append({
            "event_type": "invalid_energy_type",
            "reason": f"Energy must be numeric, got: {type(energy).__name__}"
        })

    parsed_timestamp = None
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp)
    except ValueError:
        errors.append({
            "event_type": "invalid_timestamp",
            "reason": f"Invalid timestamp format: {timestamp}"
        })

    if room_is_known and energy_is_numeric:
        min_energy, max_energy = settings.allowed_rooms[room_id]
        if not (min_energy <= energy <= max_energy):
            errors.append({
                "event_type": "out_of_range_energy",
                "reason": (
                    f"Energy out of allowed range for {room_id}: "
                    f"{energy} not in [{min_energy}, {max_energy}]"
                )
            })

    expected_signature = generate_expected_signature(reading_data)
    if not hmac.compare_digest(provided_signature, expected_signature):
        errors.append({
            "event_type": "invalid_signature",
            "reason": "Message signature validation failed"
        })

    if parsed_timestamp is not None and device_id in settings.trusted_devices:
        if is_replay_attack(device_id, room_id, timestamp):
            errors.append({
                "event_type": "replay_attack",
                "reason": (
                    f"Replay attack detected for device {device_id} in {room_id}. "
                    f"Timestamp {timestamp} is duplicated or older than the last accepted message for this room stream."
                )
            })

    if errors:
        return False, errors

    return True, []


def save_reading_to_db(reading_data: dict):
    db: Session = SessionLocal()
    try:
        parsed_timestamp = datetime.fromisoformat(reading_data["timestamp"])

        db_reading = models.EnergyReading(
            room_id=reading_data["room_id"],
            energy=reading_data["energy"],
            timestamp=parsed_timestamp
        )
        db.add(db_reading)
        db.commit()
        db.refresh(db_reading)
        print(f"Saved from MQTT to DB: {db_reading.id} - {db_reading.room_id}")
    except Exception as e:
        db.rollback()
        print(f"Failed to save MQTT reading to DB: {e}")
    finally:
        db.close()


def on_connect(client, userdata, flags, rc, properties=None):
    print(f"MQTT on_connect rc = {rc}")
    if rc == 0:
        print("Connected to MQTT broker successfully.")
        client.subscribe(settings.mqtt_topic)
        print(f"Subscribed to topic: {settings.mqtt_topic}")
    else:
        print(f"Failed to connect to MQTT broker. rc={rc}")

def on_message(client, userdata, msg):
    payload = None
    try:
        print(f"RAW MQTT topic: {msg.topic}")
        payload = msg.payload.decode()
        print(f"Received MQTT message: {payload}")

        reading_data = json.loads(payload)

        expected_signature = generate_expected_signature(reading_data)
        print(f"Provided signature: {reading_data['signature']}")
        print(f"Expected signature: {expected_signature}")

        is_valid, validation_errors = validate_reading(reading_data)

        if not is_valid:
            for error in validation_errors:
                save_security_event(
                    event_type=error["event_type"],
                    reason=error["reason"],
                    raw_payload=payload,
                    device_id=reading_data.get("device_id"),
                    room_id=reading_data.get("room_id")
                )
                print(f"Rejected MQTT message: {error['reason']}")
            return

        update_last_seen_timestamp(
            reading_data["device_id"],
            reading_data["room_id"],
            reading_data["timestamp"]
        )
        update_device_last_seen(reading_data["device_id"])
        save_reading_to_db(reading_data)

    except Exception as e:
        save_security_event(
            event_type="malformed_payload",
            reason=str(e),
            raw_payload=payload
        )
        print(f"Error processing MQTT message: {e}")


def start_mqtt_consumer():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, 60)
    client.loop_start()
    return client


if __name__ == "__main__":
    print("Starting MQTT consumer...")
    client = start_mqtt_consumer()
    print("MQTT consumer started and listening for messages.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping MQTT consumer...")
        client.loop_stop()
        client.disconnect()
        print("MQTT consumer stopped.")