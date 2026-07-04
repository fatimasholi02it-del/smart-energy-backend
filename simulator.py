import json
import hmac
import hashlib
import random
import os
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

BACKEND_INGEST_URL = os.getenv(
    "BACKEND_INGEST_URL",
    "https://smart-energy-backend-tq02.onrender.com/ingest/reading"
)
API_KEY = os.getenv("API_KEY", "super-secret-key")
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


def send_payload(payload: dict):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    }

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                BACKEND_INGEST_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=90,
            )

            print(f"Attempt {attempt} - Status code: {response.status_code}")
            print(f"Attempt {attempt} - Response: {response.text}")

            response.raise_for_status()
            return

        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt} failed: {e}")

            if attempt == max_attempts:
                raise


def main():
    print("HTTP simulator started.")
    print(f"Target URL: {BACKEND_INGEST_URL}")
    print("-" * 60)

    for device in DEVICES:
        payload = generate_payload(device)
        print(f"Generated: {payload}")
        send_payload(payload)
        print("-" * 60)

    print("HTTP simulator finished successfully.")


if __name__ == "__main__":
    main()