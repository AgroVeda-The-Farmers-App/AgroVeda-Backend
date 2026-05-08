from flask import Blueprint, request, jsonify
import requests
import feedparser
import os
from datetime import datetime
from functools import lru_cache
import time

news_bp = Blueprint("news", __name__)

NEWSDATA_API_KEY  = os.getenv("NEWSDATA_API_KEY")
OPENWEATHER_KEY   = os.getenv("OPENWEATHER_API_KEY")

JUNK_URLS   = ["quiz","testbook","sscadda","gradeup","oliveboard","exampur","adda247","mocktest","currentaffairs"]
JUNK_TITLES = ["quiz","mcq","objective question","exam","test series","mock test","current affairs pdf"]

# Simple in-memory cache {key: (timestamp, data)}
_cache = {}
CACHE_TTL = 1800  # 30 minutes

def cache_get(key):
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None

def cache_set(key, data):
    _cache[key] = (time.time(), data)

def is_junk(article):
    url   = article.get("link", "").lower()
    title = article.get("title", "").lower()
    return any(j in url for j in JUNK_URLS) or any(j in title for j in JUNK_TITLES)

def format_date(s):
    try:    return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except: return s[:10] if s else ""

def fetch_newsdata(queries, size=9):
    cache_key = f"news_{'_'.join(queries)}"
    cached = cache_get(cache_key)
    if cached: return cached

    all_articles, seen = [], set()
    for q in queries:
        if len(all_articles) >= size: break
        try:
            r = requests.get("https://newsdata.io/api/1/news", timeout=8, params={
                "apikey": NEWSDATA_API_KEY, "q": q,
                "country": "in", "language": "en", "size": size
            })
            for a in r.json().get("results", []):
                if is_junk(a) or a.get("title", "") in seen: continue
                seen.add(a.get("title", ""))
                all_articles.append({
                    "title":       a.get("title", ""),
                    "description": (a.get("description") or a.get("content") or "")[:200],
                    "link":        a.get("link", ""),
                    "image_url":   a.get("image_url", ""),
                    "source":      a.get("source_name") or a.get("source_id", ""),
                    "pubDate":     format_date(a.get("pubDate", "")),
                })
        except Exception as e:
            print(f"[News] fetch error: {e}")
            continue

    result = all_articles[:size]
    cache_set(cache_key, result)
    return result

def fetch_rss(feeds, max_per_feed=3):
    cache_key = f"rss_{'_'.join(feeds)}"
    cached = cache_get(cache_key)
    if cached: return cached

    articles, seen = [], set()
    for url in feeds:
        try:
            feed  = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                if count >= max_per_feed: break
                title = entry.get("title", "")
                if title in seen: continue
                seen.add(title)
                articles.append({
                    "title":       title,
                    "link":        entry.get("link", ""),
                    "description": entry.get("summary", "")[:200],
                    "pubDate":     entry.get("published", "")[:16],
                    "source":      feed.feed.get("title", ""),
                    "image_url":   "",
                })
                count += 1
        except Exception as e:
            print(f"[RSS] {url} error: {e}")
            continue

    cache_set(cache_key, articles)
    return articles


# ── GET /news?tab=general|organic|msp|agritech ───────────────────
@news_bp.route("/news", methods=["GET"])
def get_news():
    tab = request.args.get("tab", "general")

    if tab == "general":
        articles = fetch_newsdata([
            "agriculture India farming",
            "farmer India crop harvest",
            "Indian agriculture ministry"
        ])
    elif tab == "organic":
        articles = fetch_newsdata([
            "organic farming India",
            "natural farming India zero budget",
            "organic certification India farmer"
        ])
    elif tab == "msp":
        articles = fetch_newsdata([
            "minimum support price India wheat rice",
            "mandi price crop India market",
            "PM-KISAN farmer income India"
        ])
    elif tab == "agritech":
        articles = fetch_rss([
            "https://krishijagran.com/feed",
            "https://justagriculture.in/feed",
            "https://eng.ruralvoice.in/feed",
            "https://agrifarming.in/feed",
        ])
    else:
        return jsonify({"error": "Invalid tab"}), 400

    return jsonify({"articles": articles, "tab": tab}), 200


# ── GET /weather?city=Kolkata ─────────────────────────────────────
@news_bp.route("/weather", methods=["GET"])
def get_weather():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "city parameter required"}), 400

    if not OPENWEATHER_KEY:
        return jsonify({"error": "OPENWEATHER_API_KEY not configured"}), 500

    cache_key = f"weather_{city.lower()}"
    cached = cache_get(cache_key)
    if cached: return jsonify(cached), 200

    try:
        # Current weather
        r = requests.get("https://api.openweathermap.org/data/2.5/weather", params={
            "q": f"{city},IN", "appid": OPENWEATHER_KEY, "units": "metric"
        }, timeout=8)

        if r.status_code != 200:
            return jsonify({"error": f"City not found: {city}"}), 404

        w = r.json()

        # 5-day forecast
        fr = requests.get("https://api.openweathermap.org/data/2.5/forecast", params={
            "q": f"{city},IN", "appid": OPENWEATHER_KEY, "units": "metric"
        }, timeout=8).json()

        seen_days, forecast = set(), []
        for item in fr.get("list", []):
            day = item["dt_txt"][:10]
            if day not in seen_days:
                seen_days.add(day)
                forecast.append({
                    "day":   datetime.strptime(day, "%Y-%m-%d").strftime("%a %d %b"),
                    "temp":  round(item["main"]["temp"]),
                    "desc":  item["weather"][0]["description"].title(),
                    "icon":  item["weather"][0]["main"],
                })
            if len(forecast) == 5: break

        # Farming advisory
        temp = w["main"]["temp"]
        hum  = w["main"]["humidity"]
        cond = w["weather"][0]["main"]

        if cond == "Rain":
            advisory = {"type": "info", "text": "Rain detected — Avoid spraying pesticides today. Good time for transplanting."}
        elif cond == "Thunderstorm":
            advisory = {"type": "warning", "text": "Thunderstorm — Keep farm workers indoors. Secure equipment and young crops."}
        elif temp > 38:
            advisory = {"type": "warning", "text": "Very high temperature — Irrigate early morning or evening. Mulch to retain moisture."}
        elif temp < 10:
            advisory = {"type": "info", "text": "Cold conditions — Protect seedlings. Good time for Rabi crop sowing."}
        elif hum > 80:
            advisory = {"type": "warning", "text": "High humidity — Watch for fungal diseases. Ensure good air circulation."}
        else:
            advisory = {"type": "success", "text": "Good farming conditions — Suitable for field work, spraying and irrigation."}

        result = {
            "city":        w["name"],
            "temp":        round(w["main"]["temp"], 1),
            "humidity":    w["main"]["humidity"],
            "wind_speed":  w["wind"]["speed"],
            "condition":   w["weather"][0]["description"].title(),
            "condition_main": cond,
            "advisory":    advisory,
            "forecast":    forecast,
        }

        cache_set(cache_key, {"data": result})
        return jsonify({"data": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500