from flask import Blueprint, request, jsonify
import numpy as np
import pandas as pd
import requests as req
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from datetime import datetime, timedelta
import pytz
import os

weather_bp = Blueprint("weather", __name__)

API_KEY  = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5/"

# ── Load historical CSV once at startup ──────────────────────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH     = os.path.join(BASE_DIR, "weather.csv")
_hist        = None
_rain_model  = None
_temp_model  = None
_humid_model = None
_encoder     = None

COMPASS_POINTS = [
    ("N",   0,     11.25), ("NNE", 11.25,  33.75), ("NE",  33.75,  56.25),
    ("ENE", 56.25, 78.75), ("E",   78.75, 101.25), ("ESE",101.25, 123.75),
    ("SE", 123.75,146.25), ("SSE",146.25, 168.75), ("S",  168.75, 191.25),
    ("SSW",191.25,213.75), ("SW", 213.75, 236.25), ("WSW",236.25, 258.75),
    ("W",  258.75,281.25), ("WNW",281.25, 303.75), ("NW", 303.75, 326.25),
    ("NNW",326.25,348.75), ("N",  348.75, 360),
]

def deg_to_compass(deg):
    wind_deg = deg % 360
    return next(pt for pt, start, end in COMPASS_POINTS if start <= wind_deg < end)

def load_and_train():
    global _hist, _rain_model, _temp_model, _humid_model, _encoder
    if not os.path.exists(CSV_PATH):
        print(f"[Weather] ⚠️  weather.csv not found at {CSV_PATH}")
        return False
    try:
        df = pd.read_csv(CSV_PATH).dropna().drop_duplicates()
        _encoder = LabelEncoder()
        df2 = df.copy()
        df2["WindGustDir"]  = _encoder.fit_transform(df2["WindGustDir"])
        df2["RainTomorrow"] = LabelEncoder().fit_transform(df2["RainTomorrow"])

        X = df2[["MinTemp","MaxTemp","WindGustDir","WindGustSpeed","Humidity","Pressure","Temp"]]
        y = df2["RainTomorrow"]
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        _rain_model = RandomForestClassifier(n_estimators=100, random_state=42)
        _rain_model.fit(X_tr, y_tr)

        def prep_forecast(col):
            vals = df[col].values
            return vals[:-1].reshape(-1,1), vals[1:]

        Xt, yt = prep_forecast("Temp")
        Xh, yh = prep_forecast("Humidity")
        _temp_model  = RandomForestRegressor(n_estimators=100, random_state=42).fit(Xt, yt)
        _humid_model = RandomForestRegressor(n_estimators=100, random_state=42).fit(Xh, yh)
        _hist = df
        print("[Weather] ✅ Models trained successfully")
        return True
    except Exception as e:
        print(f"[Weather] ❌ Training failed: {e}")
        return False

# Train on startup
load_and_train()

def predict_future(model, start, steps=5):
    preds = [start]
    for _ in range(steps):
        preds.append(float(model.predict(np.array([[preds[-1]]]))[0]))
    return [round(p, 1) for p in preds[1:]]

def get_future_times():
    tz   = pytz.timezone("Asia/Kolkata")
    now  = datetime.now(tz)
    base = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return [(base + timedelta(hours=i)).strftime("%H:00") for i in range(5)]


# ── GET /weather/current?city=Kolkata ────────────────────────────
@weather_bp.route("/weather/current", methods=["GET"])
def get_current():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "city parameter required"}), 400
    if not API_KEY:
        return jsonify({"error": "OPENWEATHER_API_KEY not set"}), 500

    r = req.get(f"{BASE_URL}weather", params={
        "q": city, "appid": API_KEY, "units": "metric"
    }, timeout=8)

    if r.status_code != 200:
        return jsonify({"error": f"City not found: {city}"}), 404

    d = r.json()
    return jsonify({
        "city":             d["name"],
        "country":          d["sys"]["country"],
        "current_temp":     round(d["main"]["temp"]),
        "feels_like":       round(d["main"]["feels_like"]),
        "temp_min":         round(d["main"]["temp_min"]),
        "temp_max":         round(d["main"]["temp_max"]),
        "humidity":         round(d["main"]["humidity"]),
        "pressure":         d["main"]["pressure"],
        "description":      d["weather"][0]["description"],
        "wind_speed":       d["wind"]["speed"],
        "wind_deg":         d["wind"]["deg"],
        "wind_compass":     deg_to_compass(d["wind"]["deg"]),
    }), 200


# ── POST /weather/predict — rain prediction + forecast ────────────
@weather_bp.route("/weather/predict", methods=["POST"])
def predict():
    if _rain_model is None:
        return jsonify({"error": "ML models not loaded. Make sure weather.csv is in backend root."}), 500

    data     = request.json or {}
    city     = data.get("city", "").strip()
    if not city:
        return jsonify({"error": "city is required"}), 400

    # Fetch live weather
    r = req.get(f"{BASE_URL}weather", params={
        "q": city, "appid": API_KEY, "units": "metric"
    }, timeout=8)
    if r.status_code != 200:
        return jsonify({"error": f"City not found: {city}"}), 404

    d = r.json()
    compass     = deg_to_compass(d["wind"]["deg"])
    compass_enc = int(_encoder.transform([compass])[0]) if compass in _encoder.classes_ else 0

    features = pd.DataFrame([{
        "MinTemp":      round(d["main"]["temp_min"]),
        "MaxTemp":      round(d["main"]["temp_max"]),
        "WindGustDir":  compass_enc,
        "WindGustSpeed": d["wind"]["speed"],
        "Humidity":     round(d["main"]["humidity"]),
        "Pressure":     d["main"]["pressure"],
        "Temp":         round(d["main"]["temp"]),
    }])

    rain_tomorrow = bool(_rain_model.predict(features)[0])

    fut_times = get_future_times()
    fut_temp  = predict_future(_temp_model,  d["main"]["temp_min"])
    fut_humid = predict_future(_humid_model, d["main"]["humidity"])

    return jsonify({
        "city":            d["name"],
        "country":         d["sys"]["country"],
        "current_temp":    round(d["main"]["temp"]),
        "feels_like":      round(d["main"]["feels_like"]),
        "temp_min":        round(d["main"]["temp_min"]),
        "temp_max":        round(d["main"]["temp_max"]),
        "humidity":        round(d["main"]["humidity"]),
        "pressure":        d["main"]["pressure"],
        "description":     d["weather"][0]["description"].title(),
        "wind_speed":      d["wind"]["speed"],
        "wind_compass":    compass,
        "rain_tomorrow":   rain_tomorrow,
        "forecast_times":  fut_times,
        "forecast_temp":   fut_temp,
        "forecast_humid":  fut_humid,
    }), 200


# ── GET /weather/status — check if CSV loaded ─────────────────────
@weather_bp.route("/weather/status", methods=["GET"])
def status():
    return jsonify({
        "csv_loaded":    _hist is not None,
        "models_ready":  _rain_model is not None,
        "csv_rows":      len(_hist) if _hist is not None else 0,
    }), 200