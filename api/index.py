from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# --- Helper Functions ---
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

# --- API Endpoints ---
@app.route('/api/autocomplete', methods=['GET'])
def autocomplete():
    user_input = request.args.get('input')
    if not user_input:
        return jsonify({"error": "Missing input parameter"}), 400

    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if not api_key:
        return jsonify({"error": "Google Maps API key not configured"}), 500

    google_places_url = (
        f"https://maps.googleapis.com/maps/api/place/autocomplete/json"
        f"?input={user_input}&components=country:IN&key={api_key}"
    )

    try:
        response = requests.get(google_places_url)
        response.raise_for_status()
        data = response.json()
        predictions = data.get("predictions", [])
        descriptions = [p.get("description", "") for p in predictions]
        # THIS IS THE FIX: Return a direct list (JSON Array)
        return jsonify(descriptions)
    except Exception as e:
        return jsonify({"error": f"Autocomplete failed: {e}"}), 500


@app.route('/api/route', methods=['GET'])
def get_route():
    try:
        start_lon, start_lat = float(request.args.get('start_lon')), float(request.args.get('start_lat'))
        end_lon, end_lat = float(request.args.get('end_lon')), float(request.args.get('end_lat'))
        
        # THIS IS THE FIX: More robust validation
        if not (8 <= start_lat <= 37 and 68 <= start_lon <= 97) or \
           not (8 <= end_lat <= 37 and 68 <= end_lon <= 97):
            return jsonify({"error": "Coordinates are outside of the supported region (India)."}), 400
            
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
        response = requests.post(ors_url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        features = data.get("features", [])
        if not features:
            return jsonify({"error": "No routes found in the response from routing service"}), 500

        route_objects, risk_scores = [], [0.3, 0.6, 0.8]
        for i, feature in enumerate(features):
            coords = feature.get("geometry", {}).get("coordinates", [])
            if coords:
                route_objects.append({
                    "polyline": encode_polyline(coords),
                    "risk_score": risk_scores[i] if i < len(risk_scores) else 1.0
                })

        return jsonify({"routes": route_objects})
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"Routing service returned an error: {e.response.text}"}), 502
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'healthy', 'message': 'Helios Backend is live!'})