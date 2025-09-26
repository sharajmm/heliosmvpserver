from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

# Load environment variables for local testing
load_dotenv()

app = Flask(__name__)

@app.route('/api/route', methods=['GET'])
def get_route():
    # --- 1. Get & Validate Coordinates ---
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

    # --- 2. Call OpenRouteService API ---
    api_key = os.getenv('ORS_API_KEY')
    if not api_key:
        return jsonify({"error": "API key not configured on the server"}), 500

    headers = {
        'Authorization': api_key,
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    # This endpoint returns the simple polyline string we need
    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car/polyline"
    
    body = {"coordinates": coordinates}

    try:
        response = requests.post(ors_url, json=body, headers=headers)
        response.raise_for_status() # Raise an error for bad status codes (4xx or 5xx)
        data = response.json()
        
        # Directly extract the polyline string
        polyline = data.get("routes", [{}])[0].get("geometry")

        if not polyline:
            return jsonify({"error": "Could not extract polyline from routing service response"}), 500

        # --- 3. Send the Final Response to the App ---
        return jsonify({
            "polyline": polyline,
            "risk_score": 0.3
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to contact routing service: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Could not parse response from routing service: {e}"}), 500

# Add a root endpoint to confirm the server is running
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'healthy',
        'message': 'Helios Backend is live!'
    })