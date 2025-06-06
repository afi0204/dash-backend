# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
# import pyodbc # REMOVE or comment out
import datetime
import re
import logging
import os
from functools import wraps
from dotenv import load_dotenv

# Assuming db_mongo_config.py is in the same directory
from db_mongo_config import get_db, errors as pymongo_errors # Import MongoDB errors for specific handling

# Load environment variables from .env file (for local development)
load_dotenv() 

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s: %(message)s')
logger = logging.getLogger(__name__)

# --- API Key Setup ---
API_KEY = os.environ.get("WATER_METER_API_KEY")
if not API_KEY:
    logger.critical("CRITICAL: WATER_METER_API_KEY environment variable not set!")
    raise ValueError("CRITICAL: WATER_METER_API_KEY environment variable not set!")
else:
    logger.info("WATER_METER_API_KEY loaded successfully.")

# --- CORS Setup ---
# For production, restrict origins
ALLOWED_CORS_ORIGINS_STR = os.environ.get("ALLOWED_CORS_ORIGINS")
if ALLOWED_CORS_ORIGINS_STR:
    origins = [origin.strip() for origin in ALLOWED_CORS_ORIGINS_STR.split(',')]
    logger.info(f"CORS configured for specific origins: {origins}")
else:
    origins = "*" # Allow all - suitable for development or if frontend is on same domain
    logger.warning("CORS is configured to allow all origins. For production deployment, set the ALLOWED_CORS_ORIGINS environment variable.")

app = Flask(__name__)
CORS(app, origins=origins)


# --- API Key Decorator --- (same as before)
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('X-API-KEY') == API_KEY:
            return f(*args, **kwargs)
        else:
            logger.warning(f"Unauthorized API access attempt to {f.__name__}.")
            return jsonify({"message": "ERROR: Unauthorized"}), 401
    return decorated_function

# --- SMS Parsing Logic --- (same as before, ensure "WH" or "Liters" is consistent)
def parse_sms_data(sms_string):
    match = re.match(r"^\s*([^,]+)\s*,\s*(\w+)\s*,\s*([^,]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*$", sms_string)
    if match:
        start_char, mid, separator_char, battery, network, wh_liters = match.groups() # Use wh_liters
        parsed = {
            "MID": mid,
            "battery_vol": battery,
            "network": network,
            "WH": wh_liters # CONSISTENCY: Use "WH" or "Liters" consistently
        }
        status_code = "OK"
        if start_char != "#S" or separator_char != "@": status_code = "FORMAT_WARN"
        else:
            try:
                if int(battery) < 3500: status_code = "LOW_BATT"
                elif int(network) < 10: status_code = "NO_SIGNAL"
            except ValueError: status_code = "DATA_ERR"
        parsed["status_code"] = status_code
        return parsed
    logger.warning(f"Failed to parse SMS: {sms_string}")
    return None

# --- Alert Checking Logic (adapts to dictionary input) ---
def check_meter_alert_status_mongo(meter_data_dict):
    if not meter_data_dict: return None
    status_code = meter_data_dict.get("status_code")
    battery_vol_str = meter_data_dict.get("battery_vol")
    network_str = meter_data_dict.get("network")
    alerts = []
    if status_code in ['FORMAT_WARN', 'DATA_ERR']: alerts.append(f"Data Issue ({status_code})")
    try:
        if battery_vol_str and int(battery_vol_str) < 3500: alerts.append("Low Battery")
    except ValueError: alerts.append("Invalid Battery Data")
    try:
        if network_str and int(network_str) < 10: alerts.append("No/Low Signal")
    except ValueError: alerts.append("Invalid Network Data")
    return ", ".join(alerts) if alerts else None


# --- API Endpoints (MongoDB versions) ---

@app.route('/api/submit-data', methods=['POST'])
@require_api_key
def submit_data():
    data = request.json
    if not data or 'sms_payload' not in data:
        logger.warning("Submit data: Missing sms_payload.")
        return jsonify({"error": "Missing sms_payload"}), 400

    raw_sms = data['sms_payload']
    parsed_data = parse_sms_data(raw_sms)

    if not parsed_data:
        return jsonify({"error": "Invalid SMS format"}), 400

    try:
        db = get_db() # Get MongoDB database object
        meter_data_collection = db["meter_data"] # Collection for readings

        # Add current server timestamp (MongoDB stores BSON Timestamps or ISODates)
        parsed_data["timestamp"] = datetime.datetime.utcnow()
        
        # Convert numeric fields from string if necessary for proper typing in MongoDB
        parsed_data["battery_vol"] = int(parsed_data["battery_vol"])
        parsed_data["network"] = int(parsed_data["network"])
        parsed_data["WH"] = int(parsed_data["WH"]) # Or Liters

        result = meter_data_collection.insert_one(parsed_data)
        logger.info(f"Data submitted to MongoDB for MID: {parsed_data['MID']}, Inserted ID: {result.inserted_id}")
        return jsonify({"message": "Data submitted successfully", "MID": parsed_data['MID']}), 201
    except pymongo_errors.PyMongoError as e:
        logger.error(f"MongoDB Error submitting data: {e}", exc_info=True)
        return jsonify({"error": "Database error (MongoDB)", "details": str(e)}), 500
    except ValueError as e: # For int conversion errors
        logger.error(f"Data type error during submission: {e}", exc_info=True)
        return jsonify({"error": "Invalid data type for numeric fields.", "details": str(e)}), 400
    except Exception as e:
        logger.error(f"General Error submitting data: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route('/api/meters', methods=['GET'])
def get_meters():
    try:
        db = get_db()
        meter_data_collection = db["meter_data"]

        # MongoDB aggregation to get the latest document for each MID
        pipeline = [
            {"$sort": {"timestamp": -1}}, 
            {"$group": {
                "_id": "$MID", 
                "latest_doc": {"$first": "$$ROOT"} 
            }},
            {"$replaceRoot": {"newRoot": "$latest_doc"}},
            {"$project": { # Explicitly project fields to ensure structure and exclude MongoDB _id
                "_id": 0, 
                "MID": 1,
                "WH": 1, 
                "timestamp": 1,
                "status_code": 1,
                "battery_vol": 1,
                "network": 1
            }},
            {"$sort": {"MID": 1}}
        ]
        
        latest_readings_cursor = meter_data_collection.aggregate(pipeline)
        
        meters_list = []
        for doc in latest_readings_cursor:
            if isinstance(doc.get("timestamp"), datetime.datetime):
                doc["timestamp"] = doc["timestamp"].strftime('%Y-%m-%d %H:%M:%S UTC')
            doc["alert_status"] = check_meter_alert_status_mongo(doc)
            meters_list.append(doc)
            
        return jsonify(meters_list)
    except pymongo_errors.PyMongoError as e:
        logger.error(f"MongoDB Error fetching meters: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch meters (MongoDB)", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"General Error fetching meters: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch meters", "details": str(e)}), 500

@app.route('/api/meter/<string:meter_id>/history', methods=['GET'])
def get_meter_history(meter_id):
    days_back_str = request.args.get('days', default="30")
    try:
        days_back = int(days_back_str)
        if days_back <= 0:
            days_back = 30 # Default to 30 if invalid
    except ValueError:
        days_back = 30
        logger.warning(f"Invalid 'days' parameter for history: {days_back_str}. Defaulting to 30.")

    start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days_back)
    
    try:
        db = get_db()
        meter_data_collection = db["meter_data"]
        
        query = {
            "MID": meter_id,
            "timestamp": {"$gte": start_date}
        }
        # Project fields to send back and exclude MongoDB's _id
        projection = {
            "_id": 0,
            "timestamp": 1,
            "WH": 1,
            "battery_vol": 1,
            "network": 1,
            "status_code": 1
        }
        history_cursor = meter_data_collection.find(query, projection).sort("timestamp", 1) # Sort ascending by time

        history_list = []
        for doc in history_cursor:
            if isinstance(doc.get("timestamp"), datetime.datetime):
                doc["timestamp"] = doc["timestamp"].strftime('%Y-%m-%d %H:%M:%S UTC')
            history_list.append(doc)
            
        return jsonify(history_list)
    except pymongo_errors.PyMongoError as e:
        logger.error(f"MongoDB Error fetching history for meter {meter_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to fetch history for meter {meter_id} (MongoDB)", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"General Error fetching history for meter {meter_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to fetch history for meter {meter_id}", "details": str(e)}), 500

# --- CRUD for Meter Metadata (Example with MongoDB) ---
# Assume a 'meters_metadata' collection
# You would add similar CREATE, READ, UPDATE, DELETE routes as before, but using pymongo

@app.route('/api/admin/meters', methods=['POST'])
@require_api_key
def create_meter_metadata():
    data = request.json
    if not data or 'MID' not in data:
        return jsonify({"error": "Missing MID"}), 400
    
    # Add type conversions and more validation as needed
    # Example: data['InstallationDate'] = datetime.datetime.strptime(data['InstallationDate'], '%Y-%m-%d')
    # Ensure MID is unique if it's your primary key here
    
    try:
        db = get_db()
        metadata_collection = db["meters_metadata"]
        
        # Check if MID already exists
        if metadata_collection.find_one({"MID": data["MID"]}):
            return jsonify({"error": f"Meter metadata with MID {data['MID']} already exists."}), 409

        data["LastModified"] = datetime.datetime.utcnow()
        result = metadata_collection.insert_one(data)
        # To return the inserted document, you might fetch it again or use the input data
        # (MongoDB insert_one doesn't return the full doc by default, just inserted_id)
        created_doc = metadata_collection.find_one({"_id": result.inserted_id})
        if created_doc and "_id" in created_doc: # Convert ObjectId to string for JSON
            created_doc["_id"] = str(created_doc["_id"])
        return jsonify(created_doc), 201
    except pymongo_errors.PyMongoError as e:
        logger.error(f"MongoDB error creating meter metadata: {e}", exc_info=True)
        return jsonify({"error": "Database error (MongoDB)", "details": str(e)}), 500
    except Exception as e:
        logger.error(f"General error creating meter metadata: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500

# Add GET (all), GET (one), PUT, DELETE for /api/admin/meters similar to the SQL version,
# but using metadata_collection.find(), .find_one(), .update_one(), .delete_one()


if __name__ == '__main__':
    # This part is for local execution, not used by Gunicorn on Render
    try:
        get_db() # Attempt to connect to DB at startup for local dev
        logger.info("MongoDB connection established for local development.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB at startup for local dev: {e}")
        # Decide if app should exit or continue without DB for local dev
    
    app.run(debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true", 
            host='0.0.0.0', 
            port=int(os.environ.get("PORT", 5000)))
    logger.info("Starting Water Meter API (local Flask server)...")