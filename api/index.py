from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

@app.route('/api/route', methods=['GET'])
def get_route():
    try:
        start_lon = request.args.get('start_lon')
        start_lat = request.args.get('start_lat')
        end_lon = request.args.get('end_lon')
        end_lat = request.args.get('end_lat')

        if not all([start_lon, start_lat, end_lon, end_lat]):
            return jsonify({"error": "Missing required coordinates"}), 400
        
        # We don't need to convert to float here, the URL will handle it as strings
    except Exception:
        return jsonify({"error": "Invalid coordinate format"}), 400

    api_key = os.getenv('ORS_API_KEY')
    if not api_key:
        return jsonify({"error": "API key not configured on the server"}), 500

    # --- THIS IS THE FIX: We are now using a simpler GET request ---
    # The coordinates and API key are passed directly in the URL.
    ors_url = (
        f"https://api.openrouteservice.org/v2/directions/driving-car"
        f"?api_key={api_key}"
        f"&start={start_lon},{start_lat}"
        f"&end={end_lon},{end_lat}"
    )

    try:
        response = requests.get(ors_url)
        response.raise_for_status()
        data = response.json()
        
        # The response from a GET request is GeoJSON, so we need to get the coordinates
        # and then encode them into a polyline string.
        coordinates = data.get("features", [{}])[0].get("geometry").get("coordinates")
        
        if not coordinates:
             return jsonify({"error": "Could not extract coordinates from routing service response"}), 500

        # Simple Polyline Encoding (precision 5)
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

        polyline = encode_polyline(coordinates)

        return jsonify({
            "polyline": polyline,
            "risk_score": 0.3
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Could not parse response: {e}"}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'healthy', 'message': 'Helios Backend is live!'})