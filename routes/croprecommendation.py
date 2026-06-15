from flask import Blueprint, request, jsonify
import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

cropn_bp = Blueprint("cropn", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_DIR = os.path.join(BASE_DIR, "saved")

os.makedirs(SAVED_DIR, exist_ok=True)

MODEL_PATH = os.path.join(SAVED_DIR, "crop_model.pkl")
ENCODER_PATH = os.path.join(SAVED_DIR, "label_encoder.pkl")
DATASET_PATH = os.path.join(BASE_DIR, "Crop_recommendation.csv")

# Train model if not found
if not os.path.exists(MODEL_PATH) or not os.path.exists(ENCODER_PATH):

    print("[CropRecommendation] Training crop recommendation model...")

    df = pd.read_csv(DATASET_PATH)

    X = df[
        [
            "N",
            "P",
            "K",
            "temperature",
            "humidity",
            "ph",
            "rainfall",
        ]
    ]

    y = df["label"]

    encoder = LabelEncoder()
    y_encoded = encoder.fit_transform(y)

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42
    )

    model.fit(X, y_encoded)

    joblib.dump(model, MODEL_PATH)
    joblib.dump(encoder, ENCODER_PATH)

    print("[CropRecommendation] Model trained and saved.")

# Load model
model = joblib.load(MODEL_PATH)
encoder = joblib.load(ENCODER_PATH)

print("[CropRecommendation] Model loaded successfully")


@cropn_bp.route("/crop/predict", methods=["POST"])
def predict_crop():

    try:
        data = request.json

        required_fields = [
            "N",
            "P",
            "K",
            "temperature",
            "humidity",
            "ph",
            "rainfall"
        ]

        for field in required_fields:
            if field not in data:
                return jsonify({
                    "error": f"Missing field: {field}"
                }), 400

        features = np.array([[
            float(data["N"]),
            float(data["P"]),
            float(data["K"]),
            float(data["temperature"]),
            float(data["humidity"]),
            float(data["ph"]),
            float(data["rainfall"])
        ]])

        prediction = model.predict(features)[0]

        crop = encoder.inverse_transform([prediction])[0]

        confidence = round(
            float(np.max(model.predict_proba(features))) * 100,
            2
        )

        return jsonify({
            "crop": crop,
            "confidence": confidence
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500