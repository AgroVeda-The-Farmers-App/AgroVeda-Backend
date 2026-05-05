from flask import Blueprint, request, jsonify
from groq import Groq
import pandas as pd
import json
import re
import os

crop_bp = Blueprint("crop", __name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Load CSV once at startup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH  = os.path.join(BASE_DIR, "niti_ayog_crop_data.csv")

try:
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    print(f"[CropCalendar] Loaded {len(df)} rows from CSV")
except Exception as e:
    df = None
    print(f"[CropCalendar] CSV load failed: {e}")


# ── GET all states ────────────────────────────────────────────────
@crop_bp.route("/crop/states", methods=["GET"])
def get_states():
    if df is None:
        return jsonify({"error": "CSV not loaded"}), 500
    states = sorted(df["State"].dropna().unique().tolist())
    return jsonify({"states": states}), 200


# ── GET crops for a state ─────────────────────────────────────────
@crop_bp.route("/crop/crops", methods=["GET"])
def get_crops():
    if df is None:
        return jsonify({"error": "CSV not loaded"}), 500
    state = request.args.get("state", "").strip()
    if not state:
        return jsonify({"error": "state parameter required"}), 400
    crops = sorted(df[df["State"] == state]["Crop Name"].dropna().unique().tolist())
    return jsonify({"crops": crops}), 200


# ── GET crop info (season, category) ─────────────────────────────
@crop_bp.route("/crop/info", methods=["GET"])
def get_crop_info():
    if df is None:
        return jsonify({"error": "CSV not loaded"}), 500
    state = request.args.get("state", "").strip()
    crop  = request.args.get("crop", "").strip()
    if not state or not crop:
        return jsonify({"error": "state and crop required"}), 400

    matches = df[(df["State"] == state) & (df["Crop Name"] == crop)]
    if matches.empty:
        return jsonify({"error": "No data found"}), 404

    row = matches.iloc[0]
    return jsonify({
        "state":    state,
        "crop":     crop,
        "season":   str(row.get("Season", "")),
        "category": str(row.get("Crop Category", "")),
    }), 200


# ── POST generate AI guide ────────────────────────────────────────
@crop_bp.route("/crop/generate", methods=["POST"])
def generate_guide():
    if not GROQ_API_KEY:
        return jsonify({"error": "GROQ_API_KEY not configured"}), 500
    if df is None:
        return jsonify({"error": "CSV not loaded"}), 500

    data   = request.json or {}
    state  = data.get("state", "").strip()
    crop   = data.get("crop", "").strip()
    season = data.get("season", "").strip()

    if not state or not crop or not season:
        return jsonify({"error": "state, crop and season are required"}), 400

    try:
        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""You are an expert agricultural advisor for Indian farmers.
Give a detailed practical farming guide for {crop} grown in {state}, India during the {season} season.

Return ONLY a valid JSON object with exactly these keys, no extra text, no markdown:
{{
  "sowing_method": "how to sow/plant this crop",
  "best_sowing_months": "e.g. June-July",
  "harvest_months": "e.g. October-November",
  "harvest_duration": "e.g. 90-120 days",
  "sun_requirements": "Full Sun / Partial Shade etc",
  "soil_type": "best soil type",
  "water_needs": "irrigation frequency and amount",
  "plant_spacing_cm": "spacing between plants in cm",
  "row_spacing_cm": "spacing between rows in cm",
  "fertilizer": "recommended fertilizer and schedule",
  "common_pests": "2-3 common pests and basic control",
  "yield_per_hectare": "expected yield",
  "market_tip": "one market or storage tip relevant to {state}",
  "pro_tip": "one expert tip specific to {season} season in {state}"
}}"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an agricultural expert. Always respond with valid JSON only. No markdown, no explanation."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        guide = json.loads(raw)

        return jsonify({
            "state":   state,
            "crop":    crop,
            "season":  season,
            "guide":   guide,
        }), 200

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned unexpected format. Please try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500