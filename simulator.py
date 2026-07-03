import json
import hmac
import hashlib
import random
import os
from datetime import datetime

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
TOPIC = os.getenv("MQTT_TOPIC", "energy/readings")
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MESSAGE_SECRET = os.getenv("MESSAGE_SECRET", "super-secret-key")

DEVICES = [
    {
        "device_id": "simulator_01",
        "building_id": "building_1",
        "room_id": "room_1",
        "energy_range": (2.2, 4.0),
    },
    {
        "device_id": "simulator_02",
        "building_id": "building_1",
        "room_id": "room_2",
        "energy_range": (1.8, 3.5),
    },
    {
        "device_id": "simulator_03",
        "building_id": "building_2",
        "room_id": "room_3",
        "energy_range": (3.0, 4.8),
    },
]


def build_signing_string(payload: dict) -> str:
    return f"{payload['device_id']}|{payload['room_id']}|{payload['energy']}|{payload['timestamp']}"


def generate_signature(payload: dict) -> str:
    signing_string = build_signing_string(payload)
    return hmac.new(
        MESSAGE_SECRET.encode(),
        signing_string.encode(),
        hashlib.sha256
    ).hexdigest()


def generate_energy(device: dict) -> float:
    min_energy, max_energy = device["energy_range"]

    value = round(random.uniform(min_energy, max_energy), 2)

    spike_chance = random.random()
    if spike_chance < 0.12:
        value = value + random.uniform(0.2, 0.6)

    value = round(min(value, max_energy), 2)
    return value


def generate_payload(device: dict) -> dict:
    payload = {
        "device_id": device["device_id"],
        "room_id": device["room_id"],
        "energy": generate_energy(device),
        "timestamp": datetime.now().isoformat(),
    }
    payload["signature"] = generate_signature(payload)
    return payload


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.tls_set()
    client.connect(BROKER_HOST, BROKER_PORT, 60)

    print("Simulator started.")
    print(f"Broker: {BROKER_HOST}:{BROKER_PORT}")
    print(f"Publishing to MQTT topic: {TOPIC}")
    print("-" * 60)

    for device in DEVICES:
        payload = generate_payload(device)
        message = json.dumps(payload)

        result = client.publish(TOPIC, message)

        if result.rc == 0:
            print(f"Generated: {payload}")
            print(f"Published successfully: {message}")
        else:
            print("Failed to publish message.")

    print("-" * 60)
    client.disconnect()
    print("Simulator finished successfully.")


if __name__ == "__main__":
    main()