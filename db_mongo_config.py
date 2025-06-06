# db_mongo_config.py
import os
from pymongo import MongoClient, errors
import logging

logger = logging.getLogger(__name__) # Assumes logger is configured in app.py

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    logger.critical("CRITICAL: MONGO_URI environment variable not set!")
    raise ValueError("CRITICAL: MONGO_URI environment variable not set!")

# MONGO_DB_NAME can be set to override the DB name in the URI or provide a default
# If the database name is part of your MONGO_URI, this can be optional or used as a check.
MONGO_DB_NAME_FROM_ENV = os.environ.get("MONGO_DB_NAME")

client = None
db_connection = None # This will store the database object

def get_mongo_db_connection():
    global client, db_connection
    # Check if we already have a valid connection
    if client and db_connection:
        try:
            client.admin.command('ping') # Check if server is available
            logger.debug("MongoDB connection still active.")
            return db_connection
        except errors.ConnectionFailure:
            logger.warning("MongoDB connection lost. Attempting to reconnect...")
            client = None # Force re-connection
            db_connection = None

    try:
        # Log only a part of the URI for security, especially in production logs
        uri_to_log = MONGO_URI.split('@')[-1] if '@' in MONGO_URI else MONGO_URI
        logger.info(f"Attempting to connect to MongoDB cluster: ...@{uri_to_log}")
        
        # Increased timeout for initial connections, especially on services like Render
        # that might have cold starts or network setup delays.
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=20000) 
        
        # The ping command will verify server availability and auth if db user requires it
        client.admin.command('ping') 
        logger.info("Successfully connected to MongoDB server (ping successful).")
        
        db_name_to_use = None
        # Option 1: Explicitly from MONGO_DB_NAME_FROM_ENV if provided
        if MONGO_DB_NAME_FROM_ENV:
            db_name_to_use = MONGO_DB_NAME_FROM_ENV
            logger.info(f"Using database from MONGO_DB_NAME env var: {db_name_to_use}")
        # Option 2: Infer from URI (if URI has /dbname)
        # MongoClient().get_database() gets the default DB from the URI.
        # Its .name attribute gives the name of that database.
        elif client.get_database().name and client.get_database().name not in ['admin', 'local', 'config']: # 'admin', 'local', 'config' are system DBs
             inferred_db_name = client.get_database().name
             db_name_to_use = inferred_db_name
             logger.info(f"Using database inferred from MONGO_URI: {db_name_to_use}")
        else:
            # Fallback if nothing specified and URI default is not a user database
            # It's better to have the DB name in the URI or MONGO_DB_NAME env var
            fallback_db_name = "WaterMeterData" # Choose a sensible default
            db_name_to_use = fallback_db_name
            logger.warning(f"MONGO_DB_NAME not set and no specific DB in URI, falling back to default: {db_name_to_use}")
        
        if not db_name_to_use: # Should not happen with above logic, but as a safeguard
            raise ValueError("Database name could not be determined. Set MONGO_DB_NAME or include it in MONGO_URI.")

        db_connection = client[db_name_to_use] # Get the database object
        logger.info(f"Connected to MongoDB database: {db_connection.name}")
        return db_connection
    except errors.ConfigurationError as e:
        logger.critical(f"MongoDB Configuration Error (likely bad MONGO_URI format or invalid options): {e}", exc_info=True)
        raise
    except errors.OperationFailure as e: # This can catch authentication errors
        logger.critical(f"MongoDB Operation Failure (often auth error - check user/pass in MONGO_URI, and DB user permissions): {e}", exc_info=True)
        raise
    except errors.ConnectionFailure as e: # This can catch network issues, server down, IP whitelist
        logger.critical(f"MongoDB Connection Failure (check MONGO_URI, Atlas IP Access List, network, cluster status): {e}", exc_info=True)
        raise
    except Exception as e: # Catch-all for other unexpected errors during connection
        logger.critical(f"An unexpected error occurred connecting to MongoDB: {e}", exc_info=True)
        raise

def get_db():
    """Returns the database connection, establishing it if necessary."""
    global db_connection
    if db_connection is None:
        # Attempt to establish connection if not already established
        # This also handles the case where an initial connection might have failed
        # and we want to retry on the first actual use.
        db_connection = get_mongo_db_connection()
    else:
        # Optionally, add a quick check if the existing connection is alive
        # This adds overhead to every get_db() call.
        # For simplicity here, we rely on the longer check in get_mongo_db_connection
        # if a reconnect is needed.
        pass
    return db_connection

# Optional: You can try to establish the connection when the module is loaded.
# If it fails, the app might not start, which can be good (fail-fast).
# However, for serverless environments or retries, lazy connection in get_db() can be better.
# try:
#    get_mongo_db_connection() # Attempt initial connection
# except Exception:
#    pass # Logger in get_mongo_db_connection already handled it. App will fail on first get_db() if still bad.