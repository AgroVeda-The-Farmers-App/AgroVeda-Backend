from flask import Blueprint, request, jsonify
import pandas as pd
import numpy as np
import joblib
import os

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

market_bp = Blueprint("market", __name__)

# =====================================================
# Paths
# =====================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_DIR = os.path.join(BASE_DIR, "saved")

os.makedirs(SAVED_DIR, exist_ok=True)

CSV_PATH = os.path.join(BASE_DIR, "market_prices.csv")

MODEL_PATH = os.path.join(SAVED_DIR, "market_price_model.pkl")

STATE_ENCODER_PATH = os.path.join(SAVED_DIR, "state_encoder.pkl")
DISTRICT_ENCODER_PATH = os.path.join(SAVED_DIR, "district_encoder.pkl")
MARKET_ENCODER_PATH = os.path.join(SAVED_DIR, "market_encoder.pkl")
COMMODITY_ENCODER_PATH = os.path.join(SAVED_DIR, "commodity_encoder.pkl")
VARIETY_ENCODER_PATH = os.path.join(SAVED_DIR, "variety_encoder.pkl")

# =====================================================
# Train Model
# =====================================================

if not os.path.exists(MODEL_PATH):

    print("[Market Predictor] Training model...")

    df = pd.read_csv(CSV_PATH)

    state_encoder = LabelEncoder()
    district_encoder = LabelEncoder()
    market_encoder = LabelEncoder()
    commodity_encoder = LabelEncoder()
    variety_encoder = LabelEncoder()

    df["State"] = state_encoder.fit_transform(df["State"].astype(str))
    df["District"] = district_encoder.fit_transform(df["District"].astype(str))
    df["Market"] = market_encoder.fit_transform(df["Market"].astype(str))
    df["Commodity"] = commodity_encoder.fit_transform(df["Commodity"].astype(str))
    df["Variety"] = variety_encoder.fit_transform(df["Variety"].astype(str))

    X = df[
        [
            "State",
            "District",
            "Market",
            "Commodity",
            "Variety"
        ]
    ]

    y = df[
        [
            "Min Price",
            "Max Price",
            "Modal Price"
        ]
    ]

    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42
    )

    model.fit(X, y)

    joblib.dump(model, MODEL_PATH)

    joblib.dump(state_encoder, STATE_ENCODER_PATH)
    joblib.dump(district_encoder, DISTRICT_ENCODER_PATH)
    joblib.dump(market_encoder, MARKET_ENCODER_PATH)
    joblib.dump(commodity_encoder, COMMODITY_ENCODER_PATH)
    joblib.dump(variety_encoder, VARIETY_ENCODER_PATH)

    print("[Market Predictor] Model trained successfully")

# =====================================================
# Load Model
# =====================================================

model = joblib.load(MODEL_PATH)

state_encoder = joblib.load(STATE_ENCODER_PATH)
district_encoder = joblib.load(DISTRICT_ENCODER_PATH)
market_encoder = joblib.load(MARKET_ENCODER_PATH)
commodity_encoder = joblib.load(COMMODITY_ENCODER_PATH)
variety_encoder = joblib.load(VARIETY_ENCODER_PATH)

df = pd.read_csv(CSV_PATH)

print("[Market Predictor] Model loaded successfully")

# =====================================================
# Dropdown APIs
# =====================================================

@market_bp.route("/market/states", methods=["GET"])
def get_states():
    return jsonify({
        "states": sorted(
            df["State"].dropna().unique().tolist()
        )
    })


@market_bp.route("/market/districts", methods=["GET"])
def get_districts():
    return jsonify({
        "districts": sorted(
            df["District"].dropna().unique().tolist()
        )
    })


@market_bp.route("/market/markets", methods=["GET"])
def get_markets():
    return jsonify({
        "markets": sorted(
            df["Market"].dropna().unique().tolist()
        )
    })


@market_bp.route("/market/commodities", methods=["GET"])
def get_commodities():
    return jsonify({
        "commodities": sorted(
            df["Commodity"].dropna().unique().tolist()
        )
    })


@market_bp.route("/market/varieties", methods=["GET"])
def get_varieties():
    return jsonify({
        "varieties": sorted(
            df["Variety"].dropna().unique().tolist()
        )
    })

# =====================================================
# Price Prediction API
# =====================================================

@market_bp.route("/market/predict", methods=["POST"])
def predict_price():

    try:

        data = request.json

        state = data.get("state")
        district = data.get("district")
        market = data.get("market")
        commodity = data.get("commodity")
        variety = data.get("variety")

        if not all([
            state,
            district,
            market,
            commodity,
            variety
        ]):
            return jsonify({
                "error": "All fields are required"
            }), 400

        if state not in state_encoder.classes_:
            return jsonify({"error": "Invalid state"}), 400

        if district not in district_encoder.classes_:
            return jsonify({"error": "Invalid district"}), 400

        if market not in market_encoder.classes_:
            return jsonify({"error": "Invalid market"}), 400

        if commodity not in commodity_encoder.classes_:
            return jsonify({"error": "Invalid commodity"}), 400

        if variety not in variety_encoder.classes_:
            return jsonify({"error": "Invalid variety"}), 400

        features = np.array([[
            state_encoder.transform([state])[0],
            district_encoder.transform([district])[0],
            market_encoder.transform([market])[0],
            commodity_encoder.transform([commodity])[0],
            variety_encoder.transform([variety])[0]
        ]])

        prediction = model.predict(features)[0]

        return jsonify({
            "min_price": round(float(prediction[0]), 2),
            "max_price": round(float(prediction[1]), 2),
            "modal_price": round(float(prediction[2]), 2)
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500