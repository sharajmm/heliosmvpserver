from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import math

load_dotenv()
app = Flask(__name__)

# --- Helper Function for Polyline Encoding ---
def encode_polyline(coords):
    result = []
    prev_lat, prev_lng = 0, 0
    for lon, lat in coords:
        lat_e5, lng_e5 = int(round(lat * 1e5)), int(round(lon * 1e5))
        d_lat, d_lng = lat_e5 - prev_lat, lng_e5 - prev_lng
        for v in (d_lat, d_lng):
            v = ~(v << 1) if v < 0 else (v << 1)
            while v >= 0x20:
                result.append(chr((0x20 | (v & 0x1f)) + 63))
                v >>= 5
            result.append(chr(v + 63))
        prev_lat, prev_lng = lat_e5, lng_e5
    return "".join(result)

# --- Helper Function to Calculate Risk Score ---
def calculate_risk_score(route):
    # Extract distance and duration from route summary
    distance = route.get("properties", {}).get("segments", [{}])[0].get("distance", 0)
    duration = route.get("properties", {}).get("segments", [{}])[0].get("duration", 0)

    # Base score calculation based on distance and duration
    score = math.log1p(distance) + math.log1p(duration)

    # Get starting coordinate for weather check
    coordinates = route.get("geometry", {}).get("coordinates", [])
    if not coordinates:
        return score  # Return base score if no coordinates available

    start_lon, start_lat = coordinates[0]

    # Fetch real-time weather data
    weather_api_key = os.getenv('OPENWEATHER_API_KEY')
    if not weather_api_key:
        return score  # Return base score if API key is not configured

    weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={start_lat}&lon={start_lon}&appid={weather_api_key}"
    try:
        weather_response = requests.get(weather_url)
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        weather_main = weather_data.get("weather", [{}])[0].get("main", "")

        # Apply penalties for adverse weather conditions
        if weather_main in ["Rain", "Drizzle", "Thunderstorm", "Fog"]:
            score *= 1.5  # Increase score by 50% for risky weather
    except Exception as e:
        pass  # Ignore weather API errors and use base score

    return score

# --- Autocomplete Endpoint ---
@app.route('/api/autocomplete', methods=['GET'])
def autocomplete():
    user_input = request.args.get('input')
    if not user_input:
        return jsonify([]) # Return empty list if no input

    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if not api_key:
        return jsonify({"error": "Google Maps API key not configured"}), 500

    google_places_url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json?input={user_input}&components=country:IN&key={api_key}"

    try:
        response = requests.get(google_places_url)
        response.raise_for_status()
        data = response.json()
        predictions = data.get("predictions", [])
        descriptions = [p.get("description", "") for p in predictions]
        # FIX: Return a direct JSON array
        return jsonify(descriptions)
    except Exception as e:
        return jsonify({"error": f"Autocomplete failed: {str(e)}"}), 500

# --- Routing Endpoint ---
@app.route('/api/route', methods=['GET'])
def get_route():
    try:
        start_lon = float(request.args.get('start_lon'))
        start_lat = float(request.args.get('start_lat'))
        end_lon = float(request.args.get('end_lon'))
        end_lat = float(request.args.get('end_lat'))
        coordinates = [[start_lon, start_lat], [end_lon, end_lat]]
    except (TypeError, ValueError, AttributeError):
        return jsonify({"error": "Invalid or missing coordinate format"}), 400

    api_key = os.getenv('ORS_API_KEY')
    if not api_key:
        return jsonify({"error": "ORS API key not configured"}), 500

    headers = {
        'Authorization': api_key,
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Content-Type': 'application/json; charset=utf-8'
    }
    body = {"coordinates": coordinates, "alternative_routes": {"target_count": 3}}
    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"

    try:
        # FIX: Using the correct POST method
        response = requests.post(ors_url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()

        features = data.get("features", [])
        if not features:
            return jsonify({"error": "No routes found"}), 500

        route_objects = []
        for feature in features:
            coords = feature.get("geometry", {}).get("coordinates", [])
            if coords:
                risk_score = calculate_risk_score(feature)
                route_objects.append({
                    "polyline": encode_polyline(coords),
                    "risk_score": risk_score
                })
        return jsonify({"routes": route_objects})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e.response.text}"}), 502
    except Exception as e:
        return jsonify({"error": f"Could not parse response: {str(e)}"}), 500

# --- Health Check Endpoint ---
@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'healthy', 'message': 'Helios Backend is live!'})