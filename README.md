 🚍 MTA Bus Delay Dashboard with Weather & Live Map

A real-time Streamlit dashboard that visualizes bus delays for selected MTA lines in NYC. It integrates live weather data to provide insights on how conditions might affect transit performance.

---

## 📊 Features

- 📍 Tracks multiple MTA bus lines (`M15`, `Q44`, `B46`)
- ⏱️ Shows delay between **scheduled** and **expected** arrival times
- 🌦️ Weather overlay with temperature, rain, and wind info via Open-Meteo
- 🗺️ Live interactive map with PyDeck
- 🔄 Auto-refreshes every 60 seconds
- 📦 Cached weather data for efficiency

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/mta-bus-delay-dashboard.git
cd mta-bus-delay-dashboard
````

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 💻 Run the App

```bash
streamlit run app.py
```

---

## 📁 Project Structure

```
├── app.py               # Main Streamlit app
├── requirements.txt     # Python dependencies
├── README.md            # Project documentation

---

## ⚠️ Notes

* Displays data for up to 3 active buses per line (`MAX_BUSES`)
* Weather API results are cached for one hour
* Auto-refreshes every 60 seconds to keep data live
* If no buses are active, dashboard will show a message

---

## 📜 License

This project is licensed under the MIT License.

---

## 🙏 Credits

* Developed by **Syed Muhammad Mudassir Naqvi**
* [MTA BusTime API](http://bustime.mta.info/wiki/Developers/SIRIVehicleMonitoring)
* [Open-Meteo Weather API](https://open-meteo.com/)
* [Streamlit](https://streamlit.io/)
