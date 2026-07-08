import requests
from datetime import datetime

# مبدئيًا نحط إحداثيات ثابتة
# لاحقًا منقدر نخليها من .env أو من settings
DEFAULT_LATITUDE = 33.5138
DEFAULT_LONGITUDE = 36.2765


def get_weather_forecast(latitude: float = DEFAULT_LATITUDE, longitude: float = DEFAULT_LONGITUDE):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}"
        f"&longitude={longitude}"
        "&hourly=temperature_2m,cloud_cover"
        "&forecast_days=2"
        "&timezone=auto"
    )

    response = requests.get(url, timeout=20)
    response.raise_for_status()
    data = response.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    cloud_cover = hourly.get("cloud_cover", [])

    if not times or not temperatures or not cloud_cover:
        return {
            "status": "error",
            "message": "Weather data is incomplete"
        }

    now = datetime.now()

    selected_index = None
    for i, t in enumerate(times):
        forecast_time = datetime.fromisoformat(t)
        if forecast_time.date() > now.date():
            selected_index = i
            break

    if selected_index is None:
        selected_index = min(len(times) - 1, 24)

    selected_temp = temperatures[selected_index]
    selected_cloud = cloud_cover[selected_index]

    if selected_cloud >= 70:
        weather_condition = "Cloudy"
        estimated_solar_generation = "Low"
    elif selected_cloud >= 40:
        weather_condition = "Partly Cloudy"
        estimated_solar_generation = "Medium"
    else:
        weather_condition = "Sunny"
        estimated_solar_generation = "High"

    return {
        "status": "ok",
        "forecast_time": times[selected_index],
        "weather_condition": weather_condition,
        "cloud_percent": selected_cloud,
        "temperature": selected_temp,
        "estimated_solar_generation": estimated_solar_generation,
    }