import streamlit as st
import requests
import time
from datetime import datetime
import pytz
import pandas as pd
import requests_cache
import openmeteo_requests
from retry_requests import retry
from streamlit_autorefresh import st_autorefresh
import pydeck as pdk

# === CONFIGURATION ===
API_KEY = st.secrets["MTA_API_KEY"]
LINES = ['M15', 'Q44', 'B46']
SLEEP_INTERVAL = 60
TIMEZONE = pytz.timezone("America/New_York")
MAX_BUSES = 3

# === WEATHER SETUP ===
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)
weather_cache = {}

st.set_page_config("📊 Bus Delay Dashboard", layout="wide")
st.title("🚍 MTA Bus Delay Dashboard with Weather & Live Map")

# Auto-refresh
st_autorefresh(interval=SLEEP_INTERVAL * 1000, limit=None, key="refresh")


def fetch_weather(lat, lon):
    key = (round(lat, 2), round(lon, 2))
    if key in weather_cache:
        return weather_cache[key]

    weather_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["precipitation", "windspeed_10m", "temperature_2m", "weathercode"],
        "timezone": "America/New_York"
    }

    try:
        responses = openmeteo.weather_api(weather_url, params=params)
        response = responses[0]
        hourly = response.Hourly()

        hourly_df = pd.DataFrame({
            "datetime": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            ).tz_convert("America/New_York"),
            "precipitation_mm": hourly.Variables(0).ValuesAsNumpy(),
            "windspeed_kmh": hourly.Variables(1).ValuesAsNumpy(),
            "temperature_C": hourly.Variables(2).ValuesAsNumpy(),
            "weathercode": hourly.Variables(3).ValuesAsNumpy()
        })

        weather_cache[key] = hourly_df
        return hourly_df

    except Exception as e:
        st.warning(f"🌧️ Weather API error: {e}")
        return pd.DataFrame()


def get_vehicle_data(line_ref):
    url = (
        f"https://bustime.mta.info/api/siri/vehicle-monitoring.json"
        f"?key={API_KEY}&LineRef={line_ref}&VehicleMonitoringDetailLevel=calls"
    )
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"❌ Failed to fetch data for {line_ref}: {e}")
        return None


def extract_delay_info(vehicle_data, line_ref):
    buses_info = []

    try:
        vehicles = vehicle_data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery'][0]['VehicleActivity']
    except (KeyError, IndexError):
        st.info(f"ℹ️ No active buses for line {line_ref}")
        return buses_info

    for i, vehicle in enumerate(vehicles):
        if i >= MAX_BUSES:
            break
        try:
            journey = vehicle['MonitoredVehicleJourney']
            vehicle_id = journey.get('VehicleRef', 'Unknown')
            onward_calls = journey.get('OnwardCalls', {}).get('OnwardCall', [])

            valid_calls = [
                call for call in onward_calls
                if call.get('ExpectedArrivalTime') and call.get('AimedArrivalTime')
                and call['ExpectedArrivalTime'] != call['AimedArrivalTime']
            ]

            if not valid_calls:
                valid_calls = [
                    call for call in onward_calls
                    if call.get('ExpectedArrivalTime') and call.get('AimedArrivalTime')
                ]

            if not valid_calls:
                continue

            stop_info = valid_calls[-1]

            expected = stop_info.get('ExpectedArrivalTime')
            scheduled = stop_info.get('AimedArrivalTime')
            lat = journey.get('VehicleLocation', {}).get('Latitude')
            lon = journey.get('VehicleLocation', {}).get('Longitude')

            if expected and scheduled and lat and lon:
                expected_dt = datetime.fromisoformat(expected).astimezone(TIMEZONE)
                scheduled_dt = datetime.fromisoformat(scheduled).astimezone(TIMEZONE)
                delay = (expected_dt - scheduled_dt).total_seconds() / 60

                weather_df = fetch_weather(lat, lon)
                if not weather_df.empty:
                    nearest = weather_df.iloc[(weather_df['datetime'] - expected_dt).abs().argsort()[:1]]
                    temp = nearest["temperature_C"].values[0]
                    wind = nearest["windspeed_kmh"].values[0]
                    precip = nearest["precipitation_mm"].values[0]
                    weather_summary = f"{temp:.1f}°C, wind {wind:.1f} km/h, rain {precip:.1f} mm"
                else:
                    weather_summary = "unknown"

                buses_info.append({
                    "Line": line_ref,
                    "Vehicle": vehicle_id,
                    "Destination": stop_info.get('StopPointName'),
                    "Delay (min)": round(delay, 1),
                    "Expected": expected_dt.strftime('%H:%M:%S'),
                    "Scheduled": scheduled_dt.strftime('%H:%M:%S'),
                    "Weather": weather_summary,
                    "lat": lat,
                    "lon": lon,
                    "color": "#00cc44" if delay <= 0 else "#ffcc00" if delay <= 5 else "#ff4444"
                })

        except (KeyError, IndexError, ValueError):
            continue

    return buses_info


# === Dashboard Start ===
timestamp = datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
st.markdown(f"### 🕒 Last Checked: {timestamp}")

all_buses = []

for line in LINES:
    st.subheader(f"🚌 Line {line}")
    data = get_vehicle_data(line)
    if data:
        buses = extract_delay_info(data, line)
        if buses:
            df = pd.DataFrame(buses)
            delay_color = df["Delay (min)"].apply(lambda d: "🟩" if d <= 0 else "🟨" if d <= 5 else "🟥")
            df["Delay (min)"] = delay_color + " " + df["Delay (min)"].astype(str)

            st.dataframe(df.drop(columns=["lat", "lon", "color"]), use_container_width=True, hide_index=True)
            all_buses.extend(buses)
        else:
            st.info("No active buses found.")

if all_buses:
    st.subheader("🗺️ Live Bus Locations with Route Overlays")
    map_df = pd.DataFrame(all_buses)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position='[lon, lat]',
        get_fill_color='[255, 140, 0]',
        get_radius=100,
        pickable=True,
        opacity=0.8,
    )

    view_state = pdk.ViewState(
        latitude=map_df["lat"].mean(),
        longitude=map_df["lon"].mean(),
        zoom=12,
        pitch=30,
    )

    tooltip = {
        "html": "<b>Line:</b> {Line} <br/><b>Delay:</b> {Delay (min)} <br/><b>Destination:</b> {Destination}",
        "style": {"color": "white"}
    }

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))

st.markdown("---")
st.caption("🔄 Auto-refreshes every 60 seconds | Built with 🚍 MTA + 🌦️ Open-Meteo")
