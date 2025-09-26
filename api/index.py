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
        
        coordinates = [[float(start_lon), float(start_lat)], [float(end_lon), float(end_lat)]]
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinate format"}), 400

    api_key = os.getenv('ORS_API_KEY')
    if not api_key:
        return jsonify({"error": "API key not configured on the server"}), 500

    # --- THIS IS THE FINAL, SIMPLIFIED HEADER FIX ---
    headers = {
        'Authorization': api_key,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car/polyline"
    body = {"coordinates": coordinates}

    try:
        response = requests.post(ors_url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        polyline = data.get("routes", [{}])[0].get("geometry")
        if not polyline:
            return jsonify({"error": "Could not extract polyline"}), 500

        return jsonify({"polyline": polyline, "risk_score": 0.3})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Could not parse response: {e}"}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'healthy', 'message': 'Helios Backend is live!'})