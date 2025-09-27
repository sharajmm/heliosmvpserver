from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# This is the standard polyline encoding algorithm
def encode_polyline(coords):
    result = []
    prev_lat = 0
    prev_lng = 0
    for lon, lat in coords:
        lat_e5 = int(round(lat * 1e5))
        lng_e5 = int(round(lon * 1e5))
        d_lat = lat_e5 - prev_lat
        d_lng = lng_e5 - prev_lng
        for value in (d_lat, d_lng):
            v = ~(value << 1) if value < 0 else (value << 1)
            while v >= 0x20:
                result.append(chr((0x20 | (v & 0x1f)) + 63))
                v >>= 5
            result.append(chr(v + 63))
        prev_lat = lat_e5
        prev_lng = lng_e5
    return "".join(result)

@app.route('/api/route', methods=['GET'])
def get_route():
    try:
        start_lon = request.args.get('start_lon')
        start_lat = request.args.get('start_lat')
        end_lon = request.args.get('end_lon')
        end_lat = request.args.get('end_lat')

        if not all([start_lon, start_lat, end_lon, end_lat]):
            return jsonify({"error": "Missing required coordinates"}), 400
        
        coordinates = [[float(start_lon), float(start_lat)], [float(end_lon), float(end_lat)]]
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinate format"}), 400

    api_key = os.getenv('ORS_API_KEY')
    if not api_key:
        return jsonify({"error": "API key not configured on the server"}), 500

    headers = {
        'Authorization': api_key,
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    # --- THIS IS THE FIX: We add the 'alternative_routes' parameter to the body ---
    body = {
        "coordinates": coordinates,
        "alternative_routes": {
            "target_count": 3
        }
    }
    
    # We use the main GeoJSON endpoint, which is the most robust
    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"

    try:
        response = requests.post(ors_url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        features = data.get("features", [])
        if not features:
            return jsonify({"error": "No routes found in the response"}), 500

        route_objects = []
        risk_scores = [0.3, 0.6, 0.8] # Our hardcoded risk scores

        for i, feature in enumerate(features):
            coords = feature.get("geometry", {}).get("coordinates", [])
            if not coords:
                continue

            polyline = encode_polyline(coords)
            route_objects.append({
                "polyline": polyline,
                "risk_score": risk_scores[i] if i < len(risk_scores) else 1.0
            })

        return jsonify({"routes": route_objects})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Could not parse response: {e}"}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'healthy', 'message': 'Helios Backend is live!'})