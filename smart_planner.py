from weather_service import get_weather_forecast
from database import SessionLocal
import models
from sqlalchemy import func
from datetime import datetime, timedelta


def get_current_consumption(minutes: int = 60):
    db = SessionLocal()
    try:
        since_time = datetime.now() - timedelta(minutes=minutes)

        avg_energy = (
            db.query(func.avg(models.EnergyReading.energy))
            .filter(models.EnergyReading.timestamp >= since_time)
            .scalar()
        )

        return round(float(avg_energy or 0), 2)

    except Exception as e:
        print(f"Database error in get_current_consumption: {e}")
        return 3.0  # fallback مؤقت

    finally:
        db.close()


def get_top_consumer(minutes: int = 60):
    db = SessionLocal()
    try:
        since_time = datetime.now() - timedelta(minutes=minutes)

        rows = (
            db.query(
                models.EnergyReading.room_id,
                func.avg(models.EnergyReading.energy).label("avg_energy"),
            )
            .filter(models.EnergyReading.timestamp >= since_time)
            .group_by(models.EnergyReading.room_id)
            .all()
        )

        if not rows:
            return {"room_id": "-", "average_energy": 0.0}

        top = max(rows, key=lambda r: float(r.avg_energy or 0))
        return {
            "room_id": top.room_id,
            "average_energy": round(float(top.avg_energy or 0), 2),
        }

    except Exception as e:
        print(f"Database error in get_top_consumer: {e}")
        return {
            "room_id": "room_1",
            "average_energy": 3.0
        }

    finally:
        db.close()


def get_battery_state():
    return {
        "battery_percentage": 20,
        "battery_status": "Low"
    }


def build_smart_plan():
    weather = get_weather_forecast()
    battery = get_battery_state()
    current_consumption = get_current_consumption()
    top_consumer = get_top_consumer()

    cloud_percent = weather.get("cloud_percent", 0)
    battery_percentage = battery.get("battery_percentage", 0)

    if battery_percentage < 25 and cloud_percent > 60:
        risk_level = "High"
        recommendation = (
            "Battery is low and tomorrow solar generation is expected to be weak. "
            "Reduce non-essential night consumption."
        )
        suggested_action = (
            "Delay washing machine, reduce cooling load, and avoid unnecessary devices after midnight."
        )

    elif battery_percentage < 25 and cloud_percent <= 60:
        risk_level = "Medium"
        recommendation = (
            "Battery is low, but tomorrow weather is acceptable. "
            "Moderate night consumption is recommended."
        )
        suggested_action = (
            "Use only necessary devices tonight and avoid high-load appliances."
        )

    elif battery_percentage >= 25 and cloud_percent > 60:
        risk_level = "Medium"
        recommendation = (
            "Battery is acceptable, but tomorrow is expected to be cloudy. "
            "Consider optimizing tonight's energy usage."
        )
        suggested_action = (
            "Keep essential loads active and postpone optional high-energy devices."
        )

    else:
        risk_level = "Low"
        recommendation = (
            "Battery level and weather forecast are favorable. "
            "Current consumption pattern is acceptable."
        )
        suggested_action = (
            "Maintain normal usage while continuing to monitor major loads."
        )

    return {
        "status": "ok",
        "forecast_time": weather.get("forecast_time"),
        "weather_condition": weather.get("weather_condition"),
        "cloud_percent": weather.get("cloud_percent"),
        "temperature": weather.get("temperature"),
        "estimated_solar_generation": weather.get("estimated_solar_generation"),
        "battery_percentage": battery_percentage,
        "battery_status": battery.get("battery_status"),
        "current_consumption": current_consumption,
        "top_consumer": top_consumer,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "suggested_action": suggested_action,
    }