from flask import Blueprint, request, jsonify
import joblib
import numpy as np
import os

yield_bp = Blueprint("yield", __name__)

# ── Load models once at startup ───────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_DIR  = os.path.join(BASE_DIR, "saved")

try:
    model       = joblib.load(os.path.join(SAVED_DIR, "xgb_yield_model.pkl"))
    le_state    = joblib.load(os.path.join(SAVED_DIR, "state_encode.pkl"))
    le_district = joblib.load(os.path.join(SAVED_DIR, "district_encode.pkl"))
    le_season   = joblib.load(os.path.join(SAVED_DIR, "season_encode.pkl"))
    le_crop     = joblib.load(os.path.join(SAVED_DIR, "crop_encode.pkl"))
    MODEL_LOADED = True
    print("[YieldPredictor] ✅ Models loaded successfully")
except Exception as e:
    MODEL_LOADED = False
    print(f"[YieldPredictor] ❌ Failed to load models: {e}")


# ── GET /yield/options — return all dropdown values ───────────────
@yield_bp.route("/yield/options", methods=["GET"])
def get_options():
    if not MODEL_LOADED:
        return jsonify({"error": "Models not loaded"}), 500
    return jsonify({
        "states":    le_state.classes_.tolist(),
        "districts": le_district.classes_.tolist(),
        "seasons":   le_season.classes_.tolist(),
        "crops":     le_crop.classes_.tolist(),
    }), 200


# ── POST /yield/predict ───────────────────────────────────────────
@yield_bp.route("/yield/predict", methods=["POST"])
def predict_yield():
    if not MODEL_LOADED:
        return jsonify({"error": "Models not loaded on server"}), 500

    data     = request.json or {}
    state    = data.get("state", "")
    district = data.get("district", "")
    season   = data.get("season", "")
    crop     = data.get("crop", "")
    area     = data.get("area", 0)

    # Validate
    if not all([state, district, season, crop]):
        return jsonify({"error": "state, district, season and crop are required"}), 400

    try:
        area = float(area)
    except:
        return jsonify({"error": "Area must be a number"}), 400

    if area <= 0:
        return jsonify({"error": "Area must be greater than 0"}), 400

    # Check values exist in encoder
    if state not in le_state.classes_:
        return jsonify({"error": f"Unknown state: {state}"}), 400
    if district not in le_district.classes_:
        return jsonify({"error": f"Unknown district: {district}"}), 400
    if season not in le_season.classes_:
        return jsonify({"error": f"Unknown season: {season}"}), 400
    if crop not in le_crop.classes_:
        return jsonify({"error": f"Unknown crop: {crop}"}), 400

    try:
        state_enc    = le_state.transform([state])[0]
        district_enc = le_district.transform([district])[0]
        season_enc   = le_season.transform([season])[0]
        crop_enc     = le_crop.transform([crop])[0]

        input_data   = np.array([[state_enc, district_enc, 2020, season_enc, crop_enc, area]])
        yield_pred   = model.predict(input_data)[0]
        production   = float(yield_pred) * area

        return jsonify({
            "state":      state,
            "district":   district,
            "season":     season,
            "crop":       crop,
            "area":       area,
            "yield_per_hectare": round(float(yield_pred), 2),
            "total_production":  round(production, 2),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500