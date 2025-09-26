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

    # --- THIS IS THE FINAL, CORRECTED HEADER BLOCK ---
    # It is simplified to the most common standard that their server accepts.
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    
    # This is the correct endpoint for getting an encoded polyline
    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car/polyline"
    
    # The coordinates are sent in the JSON body of the POST request
    body = {"coordinates": coordinates}

    try:
        response = requests.post(ors_url, json=body, headers=headers)
        response.raise_for_status() # This will raise an error for bad responses (4xx or 5xx)
        data = response.json()
        
        # The response gives us the polyline directly
        polyline = data.get("routes", [{}])[0].get("geometry")

        if not polyline:
            return jsonify({"error": "Could not extract polyline from routing service response"}), 500

        # --- 3. Send the Final Response to the App ---
        return jsonify({
            "polyline": polyline,
            "risk_score": 0.3
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"API request failed: {e}"}), 502
    except Exception as e:
        return jsonify({"error": f"Could not parse response from routing service: {e}"}), 500

# A root endpoint to confirm the server is running
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'healthy',
        'message': 'Helios Backend is live!'
    })